#include "calculator.h"

double divide(operands values) {
    if(values.value2 != 0) {
        return values.value1 / values.value2;
    } else {
        return 0.0; // should handle error properly for division by zero
    }
}
