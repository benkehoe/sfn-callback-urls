```bash
# set this
CODE_BUCKET=TODO_YOUR_BUCKET

export STACK_NAME=SfnCallbackUrls
export TEST_STACK_NAME=SfnIntegrationTestStack

# start in top-level directory
sam build
sam package --output-template-file packaged-template.yaml --s3-bucket $CODE_BUCKET
sam deploy --template-file packaged-template.yaml --stack-name $STACK_NAME --capabilities CAPABILITY_IAM

cd integration_tests
sam package --template-file template.yaml --output-template-file packaged-template.yaml --s3-bucket $CODE_BUCKET
sam deploy --template-file packaged-template.yaml --stack-name $TEST_STACK_NAME --capabilities CAPABILITY_IAM

pytest integration_tests.py
```
