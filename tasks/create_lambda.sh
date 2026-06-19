#!/bin/bash

mkdir -p ./lambda/package
cp ./tasks/process.py ./lambda
cd ./lambda
mv process.py lambda_function.py
pip install --target ./package boto3 pydantic
cd package
zip -r ../bulk_downloads_processor.zip .
cd ..
zip bulk_downloads_processor.zip lambda_function.py
rm -fR package lambda_function.py
