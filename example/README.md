# Example

This example creates a state machine that sends you an email requesting you to approve or reject a task,
and then another email confirming the result.

## Usage
```bash
NAME=YOUR_NAME
EMAIL=me@example.com
FUNC=$(aws cloudformation describe-stacks --stack-name SfnCallbackUrls --query "Stacks[0].Outputs[?OutputKey=='Function'].OutputValue" --output text)

aws cloudformation deploy --template-file template.yaml --stack-name SfnCallbackUrlsExample --parameter-overrides Email=$EMAIL CreateUrlsFunction=$FUNC --capabilities CAPABILITY_IAM

# Go to your email and confirm the SNS subscription

STATE_MACHINE=$(aws cloudformation describe-stacks --stack-name SfnCallbackUrlsExample --query "Stacks[0].Outputs[?OutputKey=='StateMachine'].OutputValue" --output text)

aws step-functions start-execution --state-machine-arn $STATE_MACHINE --input "{\"name\": \"$NAME\"}"
```
