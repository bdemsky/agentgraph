#include <math.h>
#include "calculator.h"

double square_root(operands values) {
    if(values.value1 >= 0) {
        return sqrt(values.value1);
    } else {
        return 0.0; // should handle error properly for square root of a negative number
    }
}
