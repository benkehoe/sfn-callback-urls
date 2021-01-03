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
# *** Do this part if you are deploying from SAR ***

# Visit https://serverlessrepo.aws.amazon.com/applications/arn:aws:serverlessrepo:us-east-2:866918431004:applications~sfn-callback-urls
# and deploy the application. Note the stack name you used, and set it below.

STACK_NAME=TODO_DEPLOYED_APP_STACK_NAME

# *** Do this part if you are deploying from source ***

STACK_NAME=SfnCallbackUrls

sam build --use-container && sam deploy --guided --stack-name $STACK_NAME

# *** Now, let's get to it ***

# Set these values
NAME=TODO_YOUR_NAME
EMAIL=TODO_YOUR_EMAIL

# This gets the Lambda function we call for creating callback URLs
FUNC=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='Function'].OutputValue" --output text)

# Deploy the example stack
aws cloudformation deploy --template-file example/template.yaml --stack-name SfnCallbackUrlsExample --parameter-overrides Email=$EMAIL CreateUrlsFunction=$FUNC --capabilities CAPABILITY_IAM

# Go to your email and confirm the SNS subscription

STATE_MACHINE=$(aws cloudformation describe-stacks --stack-name SfnCallbackUrlsExample --query "Stacks[0].Outputs[?OutputKey=='StateMachine'].OutputValue" --output text)

# Run the example state machine
aws stepfunctions start-execution --state-machine-arn $STATE_MACHINE --input "{\"name\": \"$NAME\"}"

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

If you want to disable encryption entirely, you can set the `DisableEncryption` stack parameter to `true`.
The consequence of disabling encryption is that the contents of a callback URL, including the token and the output you
want to send to the state machine, are inspectable. Additionally, somebody who has gotten a token they should not have
could construct a callback URL use it, and since the callback are unauthenticated this would constitute a privilege
escalation. However, it still requires that the token have previously leaked, and that the meaning of the token
(the state machine it corresponds to, etc.) is known.

The action name and type are put as query parameters on the callback URLs for convenience, to make the URLs more easily
distinguishable, but they are not trusted. The name and type are also stored in the payload, and when the callback is
processed, the two are compared and the callback is rejected if they don't match.

The callback method is unauthenticated, it will always result in a Lambda invocation. With encryption enabled, no
valid input should be able to be provided that hasn't already gone through the authentication URL creation call.
However, it is still susceptible to denial-of-wallet attacks from someone who knows the endpoint (such as by
having seen a callback URL). If this is a concern, a good course of action is to
[enable AWS WAF](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-control-access-aws-waf.html)
on the API Gateway.

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
    "actions": [ // you must provide at least one action
        {
            "name": "<a name for this action>",
            "type": "success", // this action will cause SendTaskSuccess
            "output": { // required, can be any JSON type
                "<your>": "<content>"
            },
            "response": {} // optional, see below
        },
        { // can have as many actions of the same type as you want
            "name": "<name2>",
            "type": "success",
            "output": "<a different output>"
        },
        {
            "name": "<name3>",
            "type": "failure",  // this action will cause SendTaskFailure
            "error": "<your error code>", // optional
            "cause": "<your error cause>" // optional
        },
        {
            "name": "<name4>",
            "type": "heartbeat" // this action will cause SendTaskHeartbeat (can invoke this type of callback more than once)
        }
    ],
    "expiration": "<ISO8601-formatted expiration>", // optional
    "enable_output_parameters": true // optional, and must be enabled on the stack, see below
}
```

### Actions

For each action you define, you will get a callback URL. Each action you provide has a *name* and a *type*.
The name is your label for the action. The type corresponds to what Step Functions API the callback will cause
to be invoked, and must be one of `success`, `failure`, or `heartbeat`, corresponding to the `SendTaskSuccess`,
`SendTaskFailure`, and `SendTaskHeartbeat` API calls, respectively.

For `success` actions, you must provide an `output` field, whose value will be passed to the
same field in `SendTaskSuccess`.

For `failure` options, you may optionally provide `error` and `cause` fields whose values are strings, which will be
passed to the same fields in `SendTaskFailure`.

#### Callback response specification
In every action, you can provide a response specification in the `response` field with an object like this:

```json5
{
    "redirect": "https://example.com", // if the callback is successful, redirect the user to the given URL
}
```
or this:
```json5
{
    "json": {"hello": "world"}, // choose the JSON object returned by the callback for the application/json content-type
    "html": "<html>hello, world</html>", // choose the body returned by the callback for the text/html content-type
    "text": "hello, world" // choose the body returned by the callback for the text/plain content-type
}
```

All fields are optional, and are only used when the callback is successfully processed; all errors return fixed content.
`redirect` takes precedence over the other fields.

### Expiration

You can optionally provide an `expiration` value as an
[ISO8601-formatted datetime](https://en.wikipedia.org/wiki/ISO_8601#Combined_date_and_time_representations);
if a callback is made after then, it will be rejected.

### Parameterizing callbacks

If you've got a lot of different potential successful outputs, you may find it easier to parameterize your callbacks.
This feature is disabled by default due to the security considerations described below; you have to set
the `EnableOutputParameters` stack parameter to `true`. Then, you must also opt-in when creating URLs by setting
the `enable_output_parameters` field to `true` in your request. Any URLs created without `enable_output_parameters`
set to `true` will not use parameterized output when the callbacks are processed. If `EnableOutputParameters` is
changed back to `false`, any previously-created callbacks with parameters enabled will be now rejected.

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

The JSON response on success:
```json5
{
    "transaction_id": "<the same id returned by the create call>",
    "action": {
        "name": "<the action name>",
        "type": "<the action type>"
    }
}
```

The JSON response on error:
```json5
{
    "error": "<error code>",
    "message": "<error description>"
}
```

## POST actions

If you'd like to use the body of a POST callback to send output for your task, for example with a webhook,
you can do this with `post` actions. A post action has a non-empty list of *outcomes*, which use the same form as
actions with a few extra fields. Each outcome has a *name* and a *type*, where the type is one of
`success`, `failure`, or `heartbeat`.

Each outcome has a *schema*, which must be a [JSON Schema](https://json-schema.org/) that will be evaluated
against the POST body. The first outcome whose schema validates against the body will used. If no schema
matches the POST body, the callback results in an error.

Like in an action, a `success` outcome can include an `output` field, and a `failure` outcome can have
`error` and `cause`; these are fixed values. To use the entire body of the request as the output for
a `success` outcome, use `"output_body": true` in your outcome.
To select information from the request body, you can use `output_path` to specify a
[JSONPath](https://github.com/kennknowles/python-jsonpath-rw#jsonpath-syntax). Because JSONPath expressions
can return multiple values, the output will *always* be an array; if you expect your expression to return a
single object, you must select it from the array in your state machine. Similarly, you can use `error_path`
and `cause_path`; if these return paths return a single string, it will be used, otherwise the resulting
JSON array of matches will be stringified.

Outcomes can contain responses. POST actions disable output parameters, even if the create URLs call
requests that they are enabled (other actions in such a call will have them enabled).

A sample request to create a POST action URL looks the following:

```json5
{
    "token": "<the token from Step Functions>", // required
    "actions": [ // you must provide at least one action
        {
            "name": "<a name for this action>",
            "type": "post",
            "outcomes": [
                {
                    "name": "<a name for this happy outcome>",
                    "type": "success",
                    "schema": { // require an object that looks like {"result": "good"}
                        "type": "object",
                        "properties": {
                            "result": {
                                "const": "good"
                            }
                        },
                        "required": [ "result" ]
                    },
                    "output_body": true
                },
                {
                    "name": "<a name for this sad outcome",
                    "type": "failure",
                    "schema": { // require an object that looks like {"result": "bad", "reason": "..."}
                        "type": "object",
                        "properties": {
                            "result": {
                                "const": "bad"
                            },
                            "reason": {
                                "type": "string"
                            }
                        },
                        "required": [ "result", "reason" ]
                    },
                    "error_path": "$.reason"
                }
            ]
        },
        { // can have other actions in addition to POST actions
            "name": "<name2>",
            "type": "success",
            "output": "<a different output>"
        }
    ]
}
```

This feature is disabled by default due to the security considerations described below; you have to set
the `EnablePostActions` stack parameter to `true`. If `EnablePostActions` is changed back to `false`,
any previously-created POST action callbacks will be now rejected.

### POST action security

POST actions allow arbitrary output to be passed into an unauthenticated endpoint, and are therefore
disabled by default. Users are required to provide a JSON schema to validate the body, but this can be
the empty schema.
