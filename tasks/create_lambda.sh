#!/bin/bash

rm -fR ./lambda/*
mkdir -p ./lambda/package
cp ./tasks/process.py ./lambda
cd ./lambda
mv process.py lambda_function.py
pip3 install --target ./package --platform manylinux2014_x86_64 --python-version 3.14 --only-binary=:all: --root-user-action=ignore pydantic
cd package
zip -r ../bulk_downloads_processor.zip .
cd ..
zip bulk_downloads_processor.zip lambda_function.py
rm -fR package lambda_function.py
