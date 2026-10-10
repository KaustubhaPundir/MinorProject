identification division.
program-id. check-demo.
environment division.
input-output section.
file-control.
    select report-file assign to "report.dat"
        organization is line sequential.
data division.
file section.
fd report-file.
01 report-line pic x(5).
procedure division.
    open output report-file
    move "HELLO" to report-line
    write report-line
    close report-file
    stop run.
