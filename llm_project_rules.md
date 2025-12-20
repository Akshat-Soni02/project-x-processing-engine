**Comments**
1. in the start of each file there should be a crisp comment which tells what the file does
2. Each function which is doing something not obvious should have docstring which clearly represnt what funtion does and follows standard practice of docstring
3. Inbetween comments should only be limited to non-obvious things, alerts, todos, future context etc
4. if comment is big we prefer multiline comment

**Logs**
1. Use of extra is preferred in logs while inline variable like {e} is not used.
2. debug logs which are just context less like ("Reforming data: decoding base64 message") this is just a random log which is not required neither it provides much value. so even though debug logs can be freely used, don't abuse them
3. The structure of messages in logs like Data reformation, Reforming data is not allowed. this should not be a part of logger message. Instead logger messages should be clear and crisp.
4. don't use function names etc in the logs instead follow standard practices. Keep names in the places where they might come handy for debugging later