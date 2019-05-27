# sfn-callback-urls
[AWS Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html) lets you create serverless
workflows in the form of state machines. Step Function supports long-running tasks, where Step Function gives out
a token, which you later send back along with the result of the task. The `sfn-callback-urls` application is designed
to make it easier to use these tokens in callback-based situations, like sending an email with a link to click, or
passing a callback URL to another service.

## How does it work?
You can create a long-running task in Step Functions in two ways. One is
[activities](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-activities.html), which require
a polling worker. The other is
[callback tasks](https://docs.aws.amazon.com/step-functions/latest/dg/connect-to-resource.html#connect-wait-token),
in which the token is sent out in an event (to a Lambda function, SQS queue, etc.).

Once you have the token, you call the `sfn-callback-urls` with the token and a set of potential outcomes. You receive
a URL for each outcome, which can then be passed on to something deciding the outcome. The chosen outcome URL can then
be `POST`'d or `GET`'d, and will send that outcome on to Step Functions, completing the task.

# Test it out
```bash
# set these values
NAME=TODO_YOUR_NAME
EMAIL=TODO_YOUR_EMAIL
CODE_BUCKET=TODO_YOUR_S3_BUCKET

sam build
sam package --output-template-file packaged-template.yaml --s3-bucket $CODE_BUCKET
sam deploy --template-file packaged-template.yaml --stack-name SfnCallbackUrls

FUNC=$(aws cloudformation describe-stacks --stack-name SfnCallbackUrls --query "Stacks[0].Outputs[?OutputKey=='Function'].OutputValue" --output text)

aws cloudformation deploy --template-file example/template.yaml --stack-name SfnCallbackUrlsExample --parameter-overrides Email=$EMAIL CreateUrlsFunction=$FUNC --capabilities CAPABILITY_IAM

# Go to your email and confirm the SNS subscription

STATE_MACHINE=$(aws cloudformation describe-stacks --stack-name SfnCallbackUrlsExample --query "Stacks[0].Outputs[?OutputKey=='StateMachine'].OutputValue" --output text)

aws step-functions start-execution --state-machine-arn $STATE_MACHINE --input "{\"name\": \"$NAME\"}"

# Now you will get an approve/reject email, followed by a confirmation of the same

```

## Security
`sfn-callback-urls` is entirely stateless; your token is not stored in it anywhere. Instead, the token is encoded into
the callback URL payload, along with the output. This means that if you lose the URLs and have not stored the tokens
somewhere else, you cannot cause the corresponding state machine task to complete or fail. However, this does not
mean you *should* store the tokens elsewhere. Instead, you may be able to provide a sensible timeout on your task,
or simply stop the execution entirely and start a new one. Try these approaches before squirreling away tokens.

By default, `sfn-callback-urls` creates a KMS key to encrypt callback payloads, so that having a callback URL neither
allows you to inspect the payload nor modify it before using it.
[**The default costs money!**](https://aws.amazon.com/kms/pricing/). There are two alternatives. If you have your own
KMS key, you can put the key ARN in the `EncryptionKeyArn` stack parameter, and it will use that instead of 
creating one.

If you want to disable encryption entirely, you can set the `EnableEncryption` stack parameter to `false`.
The consequence of disabling encryption is that the contents of a callback URL, including the token and the output you
want to send to the state machine, are inspectable. Additionally, somebody who has gotten a token they should not have
could construct a callback URL use it, and since the callback are unauthenticated this would constitute a privilege
escalation. However, it still requires that the token have previously leaked, and that the meaning of the token
(the state machine it corresponds to, etc.) is known.

The action name and type are put as query parameters on the callback URLs for convenience, to make the URLs more easily
distinguishable, but they are not trusted. The name and type are also stored in the payload, and when the callback is
processed, the two are compared and the callback is rejected if they don't match.

## Creating URLs

There are two ways to invoke the service: through the API, or direct to a Lambda. Both take identical input payloads.
The API base url can be found as the `Api` output of the CloudFormation stack. To create callback URLs with the API,
POST the JSON payload (with the`Content-Type` header set to `application/json`) to the `/urls` path. Or, simply invoke
the Lambda function found as the `Function` output of the stack. Permissions for both of these are given by the IAM
managed policy found as the `Policy` output of the CloudFormation stack.

### Input

```json5
{
    "token": "<the token from Step Functions>", // required
    "actions": { // you must provide at least one action
        "<a name for this action>": {
            "type": "success", // this action will cause SendTaskSuccess
            "output": { // required, must be an object (can be empty)
                "<your>": "<content>"
            },
            "response": {} // optional, see below
        },
        "<name2>": { // can have as many actions of the same type as you want
            "type": "success",
            "output": {
                "<a different>": "<output>"
            }
        },
        "<name3>": {
            "type": "failure",  // this action will cause SendTaskFailure
            "error": "<your error code>", // optional
            "cause": "<your error cause>" // optional
        },
        "<name4>": {
            "type": "heartbeat" // this action will cause SendTaskHeartbeat (can invoke callback more than once)
        }
    },
    "expiration": "<ISO8601-formatted expiration>", // optional
    "enable_output_parameters": true // optional, and must be enabled on the stack, see below
}
```

### Actions

For each action you define, you will get a callback URL. Each action you provide has a *name* and a *type*.
The name is your label for the action. The type corresponds to what Step Function API the callback will cause
to be invoked, and must be one of `success`, `failure`, or `heartbeat`, corresponding to the `SendTaskSuccess`,
`SendTaskFailure`, and `SendTaskHeartbeat` API calls, respectively.

For `success` actions, you must provide an `output` field whose value is an object, which will be passed to the
same field in `SendTaskSuccess`.

For `failure` options, you may optionally provide `error` and `cause` fields whose values are strings, which will be
passed to the same fields in `SendTaskFailure`.

#### Callback response specification
In every action, you can provide a response specification in the `response` field with an object like this:

```json5
{
    "redirect": "https://example.com", // if the callback is successful, redirect the user to the given URL
    "json": {"hello": "world"}, // choose the JSON object returned by the callback for the application/json content-type
    "html": "<html>hello, world</html>", // choose the body returned by the callback for the text/html content-type
    "text": "hello, world" // choose the body returned by the callback for the text/plain content-type
}
```

### Expiration

You can optionally provide an `expiration` value as an
[ISO8601-formatted datetime](https://en.wikipedia.org/wiki/ISO_8601#Combined_date_and_time_representations);
if a callback is made after then, it will be rejected.

### Parameterizing callbacks

If you've got a lot of different potential successful outputs, you may find it easier to parameterize your callbacks.
This feature is disabled by default; you have to set the `DisableOutputParameters` stack parameter to `false`. Then,
you must also opt-in when creating URLs by setting the `enable_output_parameters` field to `true`. Any URLs created
without `enable_output_parameters` set to `true` will not use parameterized output when the callbacks are processed.

Once set, any strings in the `output` field for a `success` action, the `error` and `cause` fields for a
`failure` action, and all the strings in the `response` object are passed through the Python 
[string.Template.substitute](https://docs.python.org/3.4/library/string.html#template-strings) function,
using all the query parameters except for the payload. In addition to the `action` and `name` query parameters
that are already there, you can use your own field name in your strings, and append values to the callback URL
query string. You can therefore create many outputs from one callback URL returned by the service. Note that
failure to provide all of the necessary parameters will cause the callback to be rejected.

#### Parameterized callback security

Note that these extra query parameters are inherently unvalidated by the service, and therefore when enabled,
someone could modify the query parameters to send unexpected output.

### Output

On success:
```json5
{
    "transaction_id": "<a unique id>", // for correlation
    "urls": {
        "<action name>": "<url>"
    },
    "expiration": "<ISO8601-formatted datetime>" // only if you provided an expiration
}
```

On error:
```json5
{
    "error": "<error code>",
    "message": "<error description>"
}
```

## Invoking the callback

You can either GET or POST the callback. The response respects the `Accept` header, supporting `application/json`,
`text/html`, and `text/plain`, defaulting to JSON otherwise. As outlined above, the response can be customized
when the callbacks are created.
