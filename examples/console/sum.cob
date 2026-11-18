identification division.
program-id. SumTwoNumbers.
environment division.
data division.
working-storage section.
77 num1 pic 9(5) value 0.
77 num2 pic 9(5) value 0.
77 result pic 9(6) value 0.
procedure division.
main-para.
    display "Enter first number: "
    accept num1
    display "Enter second number: "
    accept num2
    compute result = num1 + num2
    display "The sum of " num1 " and " num2 " is: " result
    stop run.
