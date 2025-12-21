**resources**
***postman***: https://nothing-3096.postman.co/workspace/My-Workspace~59e8967f-068e-4df0-821c-50d3c12fa651/collection/41321691-1614f987-96ed-479f-a61b-f1386b4ce4e4?action=share&source=copy-link&creator=41321691


**Retry Policy**

- The current retries are based on PubSub messages
- If a pipeline stage fails, based on the error we ACK or NACK the message which handles the retry logic
- If a stage of pipeline fails, whole pipeline is retried

**general**

- while installing additional libs: check support for py version & add the respective to the requirements file

**logging**

- DEBUG: Used for debugging purpose only [We can add any number of them]
- INFO: Used for production when a process starts [Should not be too many, must be only when a certain process starts]
- CRITICAL: Used for breaking warnings which might lead to crashings in production [Add Only when required]
- WARNING: Used for either warning user for some behaviour or warning developers about a certain scenerios [Add Only when required]

**linting**

***for linting locally run this in root directory***
```
ruff check src --fix
black src
```
Ever commit auto lints the project

**How to run project locally**
- We depend on pyproject.toml file for depedencies & setup
- Run this to create a virtual env
```
python3 -m venv venv
```

- Run this to activate venv
```
source venv/bin/activate
```

- then Run
```
pip install -e . ".[dev]"
```
this performs an "editable" installation of the Python package located in the current directory

- Now run the project with
```
uvicorn src.main:app --reload --reload-dir src
```


