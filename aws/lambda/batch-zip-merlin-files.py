def welcome():
    return "Welcome to AWS Lambda!"


def lambda_handler(event, context):
    return {"statusCode": 200, "body": welcome()}
