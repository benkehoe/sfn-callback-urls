```bash
# set this
export STACK_NAME=SfnCallbackUrls
export TEST_STACK_NAME=SfnIntegrationTestStack

# start in top-level directory
sam build --use-container
sam deploy --stack-name $STACK_NAME --capabilities CAPABILITY_IAM

cd integration_tests
sam deploy --stack-name $TEST_STACK_NAME --capabilities CAPABILITY_IAM

pytest integration_tests.py
```
