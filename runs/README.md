# Reviewed benchmark evidence

`runs/` is local and ignored by default. The small allow-list in `.gitignore` is the reviewed
evidence behind the committed reports and headline numbers. Those files contain only synthetic
prompts, public-document answers, model outputs, and timings; they contain no customer data,
credentials, host paths, or provider URLs.

Do not publish a new run just because it exists locally. A publishable run must:

1. use a committed suite and scorer;
2. record the model, runtime, parameters, and relevant host configuration;
3. contain no private input or secret;
4. have a SHA-256 entry in `evidence.yaml`;
5. regenerate a committed report without manual edits.

Exploratory, failed, private, or superseded runs remain ignored.
