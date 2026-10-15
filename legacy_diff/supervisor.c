/* Trusted Linux x86-64 supervisor. Candidate runs as nobody without capabilities.
 * ptrace covers descendants; root-owned framed output cannot be forged by them.
 * The supervisor stays alive until the host exports the bounded tmpfs workspace.
 */
#define _GNU_SOURCE
#include <sys/ptrace.h>
#include <sys/wait.h>
#include <sys/syscall.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/types.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <stddef.h>
#include <unistd.h>
#include <signal.h>
#include <grp.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <stdatomic.h>

#if !defined(__x86_64__)
#error supervisor currently supports Linux x86-64 only
#endif

static pthread_mutex_t output_lock = PTHREAD_MUTEX_INITIALIZER;
static unsigned long long stream_bytes, maximum;
static atomic_int output_event, allocation_event, storage_event, monitor_error;
static void exact_write(int fd, const void *data, size_t n) {
    const char *p=data;
    while(n) { ssize_t k=write(fd,p,n); if(k<0 && errno==EINTR) continue;
        if(k<=0) _exit(125);
        p+=k; n-=k; }
}
static void frame(char kind, const void *data, uint32_t n) {
    unsigned char header[5] = {kind, n>>24, n>>16, n>>8, n};
    exact_write(1,header,5); exact_write(1,data,n);
}
struct reader { int fd; char kind; };
static void *drain(void *arg) {
    struct reader *r=arg; char buffer[4096]; ssize_t n;
    while((n=read(r->fd,buffer,sizeof(buffer)))!=0) {
        if(n<0) { if(errno==EINTR) continue; monitor_error=1; break; }
        pthread_mutex_lock(&output_lock);
        size_t room=stream_bytes<maximum ? maximum-stream_bytes : 0;
        size_t kept=(size_t)n<room ? (size_t)n : room;
        if(kept) frame(r->kind,buffer,kept);
        stream_bytes+=n;
        if(stream_bytes>=maximum) { output_event=1; kill(-1,SIGKILL); }
        pthread_mutex_unlock(&output_lock);
    }
    close(r->fd); return NULL;
}
static long long counter(const char *file, const char *key) {
    FILE *f=fopen(file,"r"); char word[80]; long long value, result=-1;
    if(!f) return -1;
    while(fscanf(f,"%79s %lld",word,&value)==2) if(!strcmp(word,key)) result=value;
    fclose(f); return result;
}
static void check_storage(void) {
    /* A full tmpfs may return a short successful write instead of ENOSPC.
     * Check at both syscall boundaries, including before unlink/truncate,
     * so deleting that temporary output cannot erase the event. */
    const char *paths[]={"/work","/tmp","/dev/shm"};
    for(int i=0;i<3;i++) {
        struct statvfs s;
        if(statvfs(paths[i],&s)) { monitor_error=1; continue; }
        if(!s.f_bavail || !s.f_favail) storage_event=1;
    }
}
/* Kernel ABI of PTRACE_GET_SYSCALL_INFO, independent of libc header version. */
struct syscall_info {
    uint8_t op; uint8_t pad[3]; uint32_t arch; uint64_t ip, sp;
    union { struct { uint64_t nr, args[6]; } entry;
            struct { int64_t rval; uint8_t is_error; } exit; } data;
};
static void directories(char *path) {
    size_t length=strlen(path);
    if(strncmp(path,"/work/",6) || strstr(path,"/../") || (length>=3 && !strcmp(path+length-3,"/.."))) _exit(125);
    for(char *p=path+6; *p; p++) if(*p=='/') { *p=0; mkdir(path,0777); chmod(path,0777); *p='/'; }
    mkdir(path,0777); chmod(path,0777);
}
static int restrict_async_io(void) {
    /* Async kernel I/O reports errors through shared memory, outside syscall
     * return tracing. Deny it rather than claim evidence we cannot observe. */
    struct sock_filter filter[] = {
        BPF_STMT(BPF_LD|BPF_W|BPF_ABS, offsetof(struct seccomp_data,nr)),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K, 425, 8, 0), /* io_uring_setup */
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K, 426, 7, 0),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K, 427, 6, 0),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K, __NR_io_setup, 5, 0),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K, __NR_io_destroy, 4, 0),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K, __NR_io_getevents, 3, 0),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K, __NR_io_submit, 2, 0),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K, __NR_io_cancel, 1, 0),
        BPF_STMT(BPF_RET|BPF_K, SECCOMP_RET_ALLOW),
        BPF_STMT(BPF_RET|BPF_K, SECCOMP_RET_ERRNO|EPERM)
    };
    struct sock_fprog program={sizeof(filter)/sizeof(filter[0]),filter};
    return prctl(PR_SET_SECCOMP,SECCOMP_MODE_FILTER,&program);
}
int main(int argc, char **argv) {
    if(argc<4 || getuid()!=0) return 125;
    maximum=strtoull(argv[1],NULL,10);
    int count=atoi(argv[2]), start=3+count;
    if(!maximum || count<0 || start>=argc) return 125;
    umask(0);
    for(int i=3;i<start;i++) directories(argv[i]);
    long long p0=counter("/sys/fs/cgroup/pids.events","max");
    long long m0=counter("/sys/fs/cgroup/memory.events","max");
    long long o0=counter("/sys/fs/cgroup/memory.events","oom_kill");
    if(p0<0 || m0<0 || o0<0) return 125;
    int out[2],err[2]; if(pipe(out)||pipe(err)) return 125;
    pid_t child=fork(); if(child<0) return 125;
    if(!child) {
        close(out[0]);close(err[0]); dup2(out[1],1);dup2(err[1],2);close(out[1]);close(err[1]);
        if(setgroups(0,NULL)||setgid(65534)||setuid(65534)||prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0)) _exit(125);
        if(restrict_async_io()) _exit(125);
        if(ptrace(PTRACE_TRACEME,0,0,0)<0) _exit(125);
        raise(SIGSTOP); execvp(argv[start],argv+start); _exit(125);
    }
    close(out[1]);close(err[1]); close(0);
    struct reader readers[2]={{out[0],'O'},{err[0],'E'}}; pthread_t threads[2];
    int status, exit_code=125, signaled=0, live=1, executed=0;
    if(waitpid(child,&status,0)!=child || !WIFSTOPPED(status)) return 125;
    long flags=PTRACE_O_TRACESYSGOOD|PTRACE_O_TRACEFORK|PTRACE_O_TRACEVFORK|PTRACE_O_TRACECLONE|PTRACE_O_TRACEEXEC|PTRACE_O_EXITKILL;
    if(ptrace(PTRACE_SETOPTIONS,child,0,flags)<0) return 125;
    for(int i=0;i<2;i++) if(pthread_create(&threads[i],NULL,drain,&readers[i])) return 125;
    if(ptrace(PTRACE_SYSCALL,child,0,0)<0) return 125;
    while(live) {
        pid_t pid=waitpid(-1,&status,__WALL);
        if(pid<0) { if(errno==EINTR) continue; monitor_error=1; break; }
        if(WIFEXITED(status)||WIFSIGNALED(status)) {
            live--; if(pid==child) { signaled=WIFSIGNALED(status); exit_code=signaled ? 128+WTERMSIG(status) : WEXITSTATUS(status); } continue;
        }
        if(!WIFSTOPPED(status)) { monitor_error=1; break; }
        int sig=WSTOPSIG(status), event=(unsigned)status>>16, deliver=0;
        if(event==PTRACE_EVENT_EXEC && pid==child) executed=1;
        if(event==PTRACE_EVENT_FORK||event==PTRACE_EVENT_VFORK||event==PTRACE_EVENT_CLONE) {
            live++;
        }
        if(sig==(SIGTRAP|0x80)) {
            struct syscall_info info; memset(&info,0,sizeof(info));
            if(ptrace(0x420e,pid,sizeof(info),&info)<0) { monitor_error=1; break; }
            /* i386/x32 compatibility syscalls are outside this monitor's ABI. */
            if(info.arch!=0xc000003e || (info.op==1 && (info.data.entry.nr & 0x40000000))) { monitor_error=1; break; }
            check_storage();
            if(info.op==2 && info.data.exit.is_error) {
                long e=-info.data.exit.rval;
                if(e==ENOSPC||e==EDQUOT||e==EFBIG) storage_event=1;
                if(e==ENOMEM) allocation_event=1;
            }
        } else if(!event && sig==SIGSTOP) {
            siginfo_t info;
            if(ptrace(PTRACE_GETSIGINFO,pid,0,&info)<0 || info.si_pid!=0) { monitor_error=1; break; }
        } else if(!event) {
            deliver=sig;
            if(sig==SIGBUS || sig==SIGXFSZ) storage_event=1;
        }
        if(ptrace(PTRACE_SYSCALL,pid,0,deliver)<0 && errno!=ESRCH) { monitor_error=1; break; }
    }
    if(monitor_error) {
        kill(-1,SIGKILL);
        /* Reap ptrace stops as well as exits before joining pipe readers. */
        pid_t pid;
        while((pid=waitpid(-1,&status,__WALL))>0)
            if(WIFSTOPPED(status)) ptrace(PTRACE_CONT,pid,0,SIGKILL);
    }
    for(int i=0;i<2;i++) pthread_join(threads[i],NULL);
    long long p1=counter("/sys/fs/cgroup/pids.events","max");
    long long m1=counter("/sys/fs/cgroup/memory.events","max");
    long long o1=counter("/sys/fs/cgroup/memory.events","oom_kill");
    if(p1<p0 || m1<m0 || o1<o0 || !executed) monitor_error=1;
    char report[1024];
    int len=snprintf(report,sizeof(report),"{\"version\":1,\"complete\":%s,\"exit_code\":%d,\"signaled\":%s,\"pids_max_events\":%lld,\"memory_max_events\":%lld,\"oom_kills\":%lld,\"storage_error\":%s,\"allocation_error\":%s,\"stream_limit\":%s}",monitor_error?"false":"true",exit_code,signaled?"true":"false",p1-p0,m1-m0,o1-o0,storage_event?"true":"false",allocation_event?"true":"false",output_event?"true":"false");
    frame('M',report,len);
    for(;;) pause();
}
