```bash
# start in top-level directory
sam build
sam package --output-template-file packaged-template.yaml --s3-bucket YOUR_BUCKET
sam deploy --template-file packaged-template.yaml --stack-name SfnCallbackUrls

cd integration_test
sam package --template-file template.yaml --output-template-file packaged-template.yaml --s3-bucket YOUR_BUCKET
sam deploy --stack-name SfnIntegrationTestStack
python test_client.py --stack SfnCallbackUrls --test-stack SfnIntegrationTestStack
```
