      ******************************************************************
      * Author: Erik Eriksen
      * Date: 2021-01-13
      * Purpose: Report writer test application.
      * Tectonics: cobc
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. compact-report.

       environment division.
       input-output section.
       file-control.

           select fd-test-input-file
           assign to "orders.dat"
           organization is line sequential.

           select fd-report-file assign to "summary.dat".

       DATA DIVISION.
       FILE SECTION.

           fd  fd-test-input-file.
           01  f-test-record.
               05  f-test-student-id                   pic 9(3).
               05  f-test-student-name                 pic x(8).
               05  f-test-major                        pic x(2).
               05  f-test-num-courses                  pic 9(1).


           fd  fd-report-file
           report is r-test-report.

       WORKING-STORAGE SECTION.

           01  ws-eof-sw                           pic a value 'N'.
               88  ws-eof                          value 'Y'.
               88  ws-not-eof                      value 'N'.

       report section.
           rd  r-test-report
           page limit is 24
           heading is 1
           first detail 5
           last detail 16
           footing 20.

           01  report-header type report heading.
               05  line 1 column 3
                   pic x(14) value "Compact Orders".

               05  line 2.
                   10  column 30
                       pic x(4) value "PAGE".

                   10  column 35
                       pic zz9 source page-counter.

           01  report-line type detail line plus 1.
               05  column 2 pic 9(3) source f-test-student-id.
               05  column 8 pic x(8) source f-test-student-name.
               05  column 20 pic x(2) source f-test-major.
               05  column 26 pic 9(1) source f-test-num-courses.


       PROCEDURE DIVISION.
       main-procedure.

           display "Starting test report program."

           move 'N' to ws-eof-sw

           open input fd-test-input-file output fd-report-file
               display "Init test report."
               initiate r-test-report

               perform until ws-eof
                   read fd-test-input-file
                       at end set ws-eof to true
                   end-read
                   display "Generate report line."
                   generate report-line

               end-perform

               display "Terminate report."
               terminate r-test-report
           close fd-test-input-file fd-report-file

           display "Done."
           goback.


       populate-input-file.

           open extend fd-test-input-file

      *         move 3345 to ws-student-id
      *         move "Test Name2" to ws-student-name
      *         move "PHY" to ws-major
      *         move 12 to ws-num-courses

      *         move ws-student-record to f-test-record

               write f-test-record
           close fd-test-input-file


           exit paragraph.

       END PROGRAM compact-report.
