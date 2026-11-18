       identification division.
       program-id. divide-rounded.
       environment division.
       input-output section.
       file-control.
           select input-file assign to "amounts.dat"
               organization is line sequential.
           select output-file assign to "results.dat"
               organization is line sequential.
       data division.
       file section.
       fd input-file.
       01 input-record.
           05 amount pic s9(3)v999 sign leading separate.
       fd output-file.
       01 output-record.
           05 result-value pic s9(3)v99 sign leading separate.
           05 arithmetic-status pic x.
       working-storage section.
       01 eof-switch pic a value 'N'.
           88 at-eof value 'Y'.
       procedure division.
       main-procedure.
           open input input-file output output-file
           perform until at-eof
               read input-file
                   at end set at-eof to true
                   not at end
                       move "N" to arithmetic-status
                       compute result-value
                           rounded = amount / amount end-compute
                       write output-record
               end-read
           end-perform
           close input-file output-file
           goback.
       end program divide-rounded.
