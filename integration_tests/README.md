```bash
# set this
CODE_BUCKET=TODO_YOUR_BUCKET

export STACK_NAME=SfnCallbackUrls
export TEST_STACK_NAME=SfnIntegrationTestStack

# start in top-level directory
sam build --use-container
sam deploy --stack-name $STACK_NAME --capabilities CAPABILITY_IAM --s3-bucket $CODE_BUCKET

cd integration_tests
sam deploy --stack-name $TEST_STACK_NAME --capabilities CAPABILITY_IAM --s3-bucket $CODE_BUCKET

pytest integration_tests.py
```
