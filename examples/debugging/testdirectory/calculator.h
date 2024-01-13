#ifndef __CALCULATOR_H__
#define __CALCULATOR_H__

typedef struct {
    double value1;
    double value2;
} operands;

double add(operands values);
double subtract(operands values);
double multiply(operands values);
double divide(operands values);
double sine(operands values);
double square_root(operands values);
int main(int argc, char **argv);

#endif
