```bash
# set this
CODE_BUCKET=TODO_YOUR_BUCKET

STACK_NAME=SfnCallbackUrls
TEST_STACK_NAME=SfnIntegrationTestStack

# start in top-level directory
sam build
sam package --output-template-file packaged-template.yaml --s3-bucket $CODE_BUCKET
sam deploy --template-file packaged-template.yaml --stack-name $STACK_NAME --capabilities CAPABILITY_IAM

cd integration_test
sam package --template-file template.yaml --output-template-file packaged-template.yaml --s3-bucket $CODE_BUCKET
sam deploy --template-file packaged-template.yaml --stack-name $TEST_STACK_NAME --capabilities CAPABILITY_IAM
python test_client.py --stack $STACK_NAME --test-stack $TEST_STACK_NAME
```
