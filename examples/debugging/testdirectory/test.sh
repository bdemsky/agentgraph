#!/bin/sh

exitcode=0;
# Add test case function
run_test() {
  result=$(./calculator "$1")
  if [ "$result" != "$2" ]; then
    echo "Test case failed: $1"
    echo "Expected $2, but got $result"
    exitcode=1;
  fi
}

# run tests
run_test "sin(90) + 1" "2.0"
run_test "3 * (2 + 4)" "18.0"
run_test "1/2" "0.5"
run_test "1.5 * 2.0" "3.0"
run_test "2*(1+3*(2-1))" "8.0"
run_test "0*1" "0.0"
run_test "100+200" "300.0"
run_test "300-100" "200.0"
run_test "100/100" "1.0"
run_test "2^2" "4.0"
run_test "5!" "120.0"
run_test "sqrt(4)" "2.0"
run_test "abs(-10)" "10.0"
run_test "log(1)" "0.0"
run_test "3^2" "9.0"
run_test "0^0" "1.0"  # should be undefined or error, but most calculator will return 1 by convention.
run_test "-69*(-1)" "69.0"
run_test "tan(45)" "1.0"
run_test "1/0" "inf"
run_test "sqrt(-1)" "NaN"

if [ "$exitcode" -eq "0" ]; then
  echo "All tests passed successfully."
else
  echo "One or more test cases failed."
fi
exit $exitcode
