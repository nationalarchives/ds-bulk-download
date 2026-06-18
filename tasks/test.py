import boto3

s3 = boto3.client("s3", endpoint_url="http://minio:9000")


# List zip contents
response = s3.list_objects_v2(Bucket="development")
print(response)
response = s3.list_objects_v2(Bucket="merlin-sources")
print(response)
