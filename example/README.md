# Example

This example creates a state machine that sends you an email requesting you to approve or reject a task,
and then another email confirming the result.

## Usage

First deploy sfn-callback-urls as [described in the docs)[../README.md#deploy-the-stack].

```bash
# set these
NAME="YOUR_NAME"
EMAIL="me@example.com"
STACK_NAME=SfnCallbackUrls # the deployed sfn-callback-urls stack
EXAMPLE_STACK_NAME=SfnCallbackUrlsExample # the name you want the example stack deployed as


FUNC=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='Function'].OutputValue" --output text)

aws cloudformation deploy --template-file template.yaml --stack-name "$EXAMPLE_STACK_NAME" --parameter-overrides "Email=$EMAIL" "CreateUrlsFunctionArn=$FUNC" --capabilities CAPABILITY_IAM

# Go to your email and confirm the SNS subscription

STATE_MACHINE=$(aws cloudformation describe-stacks --stack-name "$EXAMPLE_STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='StateMachine'].OutputValue" --output text)

aws stepfunctions start-execution --state-machine-arn "$STATE_MACHINE" --input "{\"name\": \"$NAME\"}"
```

## Details

The state machine has two states, `RequestApproval` and `SendConfirmation`. `RequestApproval` sends an email with two URLs, one for "approve" and one for "reject", and waits for the response. Once the response has been received (that is, one of the links in the email has been clicked, invoking the sfn-callback-urls API), it proceeds to the `SendConfirmation` state, which will send another email with the result.

The input to the state machine is a JSON object of the form `{"name": "John Doe"}`. The email address must be supplied to the stack because the SNS subscription is created there.

The "approve" link causes the state to succeed and proceed to `SendConfirmation`. The "reject" link causes the state to fail, which is caught and also proceeds to `SendConfirmation` (but in an actual state machine would likely trigger a different path).

The links expire after 5 minutes. After this point, it's not possible for the user to trigger the state to finish, so the state itself *also* times out after 5 minutes. The expiration time can be adjusted by changing the `ApprovalRequestTimeoutSeconds` stack parameter. Ideally the state would time out a bit after the links expire, to ensure that it's not possible for the state machine to time out and then subsequently the user clicks an unexpired link. However, to make the example simpler, they use the same timeout duration, and since the links are created after the state starts, they expire after the state times out. If the state timeout is triggered, it still proceeds to `SendConfirmation`. If an unexpired link is clicked when the state has timed out, the user will see an error result.
