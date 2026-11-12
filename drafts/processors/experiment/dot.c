/* dot.c: the dot product, the small loop at the centre of most AI arithmetic. */
#include <stdio.h>

float dot(const float *a, const float *b, int n) {
    float sum = 0.0f;
    for (int i = 0; i < n; i++)
        sum += a[i] * b[i];
    return sum;
}

int main(void) {
    float a[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    float b[8] = {8, 7, 6, 5, 4, 3, 2, 1};
    printf("%.1f\n", dot(a, b, 8));
    return 0;
}
