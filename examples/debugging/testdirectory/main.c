#include <stdio.h>
#include "calculator.h"

int main(int argc, char **argv) {
    if(argc <= 1) {
        printf("No expression provided.\n");
        return 1;
    }
    
    double result = 0.0;
    operands values;
    
    for(int i = 1; i < argc; i += 2) {
        if(i == 1) {
            values.value1 = atof(argv[i]);
            result = values.value1;
            continue;
        }
        
        values.value1 = result;
        values.value2 = atof(argv[i+1]);
        
        switch(argv[i][0]) {
            case '+':
                result = add(values);
                break;
            case '-':
                result = subtract(values);
                break;
            case '*':
                result = multiply(values);
                break;
            case '/':
                if(values.value2 == 0.0) {
                    printf("Error: Division by zero.\n");
                    return 1;
                }
                result = divide(values);
                break;
            default:
                printf("Error: Unknown operator %c.\n", argv[i][0]);
                return 1;
        }
    }
    
    printf("%f\n", result);
    return 0;
}
