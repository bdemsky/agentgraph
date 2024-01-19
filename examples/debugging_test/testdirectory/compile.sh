#!/bin/sh

# Compile the individual c files into object files
gcc -Wall -g -c main.c add.c subtract.c multiply.c divide.c sine.c sqrt.c

# Link all the object files together creating the executable
gcc -o calculator main.o add.o subtract.o multiply.o divide.o sine.o sqrt.o -lm
