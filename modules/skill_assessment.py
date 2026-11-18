"""Skill Assessment: short multiple-choice checks per skill (no Streamlit).

Three questions per skill is a quick check of real knowledge, not a certification.
Each entry is (question, correct answer, three wrong answers); options are shuffled per question.
"""
from __future__ import annotations

import random

QUESTIONS: dict[str, list[tuple[str, str, list[str]]]] = {
    "Python": [
        ("What does len({1, 2, 2, 3}) return?", "3", ["4", "2", "It raises an error"]),
        ("Which expression builds the list [0, 1, 4, 9, 16]?", "[x*x for x in range(5)]", ["{x*x for x in range(5)}", "(x*x for x in range(5))", "[x**2 in range(5)]"]),
        ("What does print(type([])) show?", "<class 'list'>", ["<class 'array'>", "list", "[]"]),
    ],
    "JavaScript": [
        ("Which keyword declares a block-scoped constant?", "const", ["var", "function", "def"]),
        ("What does [1, 2, 3].map(x => x * 2) return?", "[2, 4, 6]", ["6", "[1, 2, 3]", "undefined"]),
        ("What does 5 === '5' evaluate to?", "false", ["true", "undefined", "NaN"]),
    ],
    "SQL": [
        ("Which clause filters groups after GROUP BY?", "HAVING", ["WHERE", "ORDER BY", "LIMIT"]),
        ("Which JOIN keeps every row of the left table?", "LEFT JOIN", ["INNER JOIN", "CROSS JOIN", "SELF JOIN"]),
        ("What does SELECT COUNT(*) FROM t return?", "The number of rows", ["The number of columns", "The sum of all values", "The last row"]),
    ],
    "Machine Learning": [
        ("Overfitting means a model...", "does well on training data but poorly on new data", ["does poorly everywhere", "has too few parameters", "never converges"]),
        ("Which metric suits imbalanced classification better than plain accuracy?", "F1-score", ["Mean squared error", "R-squared", "Epoch count"]),
        ("What is a validation set for?", "Tuning hyperparameters and comparing models", ["Training the final weights", "Storing raw data", "Replacing the test set forever"]),
    ],
    "Deep Learning": [
        ("Which component adds non-linearity to a neuron?", "An activation function such as ReLU", ["Matrix multiplication", "The bias term", "The batch size"]),
        ("Backpropagation computes...", "gradients of the loss with respect to the weights", ["the dataset labels", "the learning rate", "the batch size"]),
        ("Which layer type is typical for image data?", "Convolutional", ["Tokenizer", "Lookup table", "Hash layer"]),
    ],
    "Cloud Computing": [
        ("IaaS provides...", "virtualised infrastructure such as virtual machines", ["ready-made software applications", "only a programming language", "physical office space"]),
        ("Elasticity means...", "scaling resources up and down with demand", ["fixed capacity", "encrypting all data", "cheaper hardware"]),
        ("Pay-as-you-go pricing means...", "you pay for what you use", ["a flat yearly fee", "it is free forever", "a one-time purchase"]),
    ],
    "AWS": [
        ("Which AWS service stores objects such as files and images?", "S3", ["EC2", "RDS", "Lambda"]),
        ("AWS Lambda lets you...", "run code without managing servers", ["host a relational database", "register domain names", "store backups only"]),
        ("Which service launches virtual servers?", "EC2", ["S3", "IAM", "CloudFront"]),
    ],
    "Docker": [
        ("A Docker image is...", "a read-only template used to create containers", ["a running process", "a virtual machine disk only", "a network"]),
        ("Which file describes how to build an image?", "Dockerfile", ["docker.json", "compose.lock", "image.cfg"]),
        ("Which command lists running containers?", "docker ps", ["docker images", "docker build", "docker pull"]),
    ],
    "Kubernetes": [
        ("The smallest deployable unit in Kubernetes is a...", "Pod", ["Node", "Cluster", "Namespace"]),
        ("Which object keeps N replicas of a Pod running and handles rollouts?", "Deployment", ["ConfigMap", "Ingress", "Secret"]),
        ("kubectl is...", "the command-line tool for the cluster API", ["a container runtime", "a cloud provider", "a YAML linter"]),
    ],
    "Git": [
        ("Which command creates a new branch and switches to it?", "git checkout -b name", ["git branch name", "git merge name", "git clone name"]),
        ("What does git clone do?", "Copies a remote repository to your machine", ["Deletes history", "Creates a tag", "Merges two branches"]),
        ("Which command lists modified and staged files?", "git status", ["git log", "git push", "git remote"]),
    ],
    "Data Structures": [
        ("Which structure is last-in, first-out?", "Stack", ["Queue", "Heap", "Graph"]),
        ("Average time to look up a key in a hash table?", "O(1)", ["O(n)", "O(log n)", "O(n log n)"]),
        ("Which structure holds the frontier in breadth-first search?", "Queue", ["Stack", "Heap", "Binary tree"]),
    ],
    "Algorithms": [
        ("Time complexity of binary search on a sorted array?", "O(log n)", ["O(n)", "O(n log n)", "O(1)"]),
        ("Which sort guarantees O(n log n) in the worst case?", "Merge sort", ["Quick sort", "Bubble sort", "Insertion sort"]),
        ("Dijkstra's algorithm requires edge weights that are...", "non-negative", ["negative", "all equal", "integers only"]),
    ],
    "MongoDB": [
        ("MongoDB stores data as...", "documents (JSON-like BSON)", ["rows in fixed tables only", "key-only strings", "graphs"]),
        ("Which operation returns documents matching a filter?", "find()", ["join()", "select_all()", "merge()"]),
        ("What is an index mainly for?", "Speeding up queries", ["Encrypting data", "Backing up data", "Deleting duplicates"]),
    ],
    "PostgreSQL": [
        ("Which keyword shows a query's execution plan?", "EXPLAIN", ["TRACE", "PLAN", "DESCRIBE ONLY"]),
        ("Which constraint uniquely identifies each row of a table?", "PRIMARY KEY", ["DEFAULT", "CHECK", "FOREIGN KEY"]),
        ("In ACID, what does the I stand for?", "Isolation", ["Indexing", "Integration", "Inheritance"]),
    ],
    "React": [
        ("Which hook adds state to a function component?", "useState", ["useRender", "useClass", "useDom"]),
        ("Props are...", "read-only inputs passed to a component", ["mutable state local to a component", "CSS classes", "server settings"]),
        ("What does the key prop help React do in lists?", "Identify which items changed", ["Style the items", "Fetch the data", "Sort the items"]),
    ],
    "Node.js": [
        ("Node.js runs JavaScript...", "on the server using the V8 engine", ["only inside browsers", "on the GPU", "inside a database"]),
        ("Which module system uses require()?", "CommonJS", ["TypeScript", "SQL", "Docker"]),
        ("What is npm?", "Node's package manager", ["A web server", "A database", "A browser"]),
    ],
    "TypeScript": [
        ("TypeScript adds to JavaScript...", "static types", ["a new runtime", "garbage collection", "multithreading"]),
        ("What happens with let x: number = 'a'?", "A compile-time error", ["It runs and x becomes 0", "x becomes undefined", "Nothing"]),
        ("An interface is used to...", "describe the shape of an object", ["create a loop", "import CSS", "run tests"]),
    ],
    "Linux": [
        ("Which command lists files in a directory?", "ls", ["cd", "pwd", "chmod"]),
        ("What does chmod 755 file set?", "Permissions: rwx for the owner, rx for others", ["The file owner", "The file size", "A symbolic link"]),
        ("Which command prints the current directory?", "pwd", ["ls -l", "whoami", "cat"]),
    ],
    "Operating Systems": [
        ("A process is...", "a program in execution", ["a file on disk", "a CPU register", "a network packet"]),
        ("Which condition is required for deadlock?", "Circular wait", ["Infinite memory", "Only one thread", "No locks at all"]),
        ("Virtual memory lets...", "programs use more address space than physical RAM", ["the CPU run faster than its clock", "the disk replace the CPU", "the network replace RAM"]),
    ],
    "Computer Networks": [
        ("Which layer does TCP belong to?", "Transport", ["Network", "Application", "Physical"]),
        ("DNS translates...", "domain names into IP addresses", ["IP addresses into MAC addresses only", "packets into frames", "ports into IPs"]),
        ("What does HTTP status 404 mean?", "Not found", ["Server error", "Forbidden", "OK"]),
    ],
    "Cybersecurity": [
        ("What best prevents SQL injection?", "Parameterised queries", ["Longer passwords", "Hiding the database", "Bigger servers"]),
        ("How should passwords be stored?", "Hashed with a slow salted hash such as bcrypt or Argon2", ["Plain text", "Base64-encoded", "XOR-ed with a key"]),
        ("Cross-site scripting (XSS) involves...", "injecting scripts into pages other users view", ["flooding a server", "stealing hard disks", "guessing PINs"]),
    ],
    "MLOps": [
        ("Model drift means...", "data or behaviour changes so accuracy degrades", ["model files grow larger", "the GPU overheats", "the code style changes"]),
        ("Experiment tracking helps...", "reproduce and compare training runs", ["compress models", "encrypt data", "rename files"]),
        ("A model registry stores...", "versioned trained models", ["raw server logs only", "SQL schemas", "Docker networks"]),
    ],
    "Data Engineering": [
        ("ETL stands for...", "Extract, Transform, Load", ["Encode, Test, Launch", "Export, Track, Log", "Edit, Tune, Lock"]),
        ("A data warehouse is optimised for...", "analytical queries over large data", ["tiny transactions", "image editing", "game saves"]),
        ("An idempotent pipeline run means...", "re-running it gives the same result", ["it can run only once", "it runs faster each time", "it never fails"]),
    ],
    "Power BI": [
        ("DAX is...", "Power BI's formula language", ["a database server", "a chart type", "a cloud region"]),
        ("A measure differs from a calculated column because it is...", "computed at query time from the filter context", ["stored for every row", "always text", "a table relationship"]),
        ("Which view is used to define relationships between tables?", "Model view", ["Report view", "Query log", "Mobile view"]),
    ],
    "Tableau": [
        ("Measures are...", "numeric values you aggregate", ["category labels", "filters", "dashboards"]),
        ("A dashboard combines...", "several worksheets and objects", ["only raw data", "only filters", "SQL schemas"]),
        ("A calculated field lets you...", "create new values from a formula", ["delete rows", "rename servers", "export PDFs only"]),
    ],
    "Generative AI": [
        ("RAG stands for...", "Retrieval-Augmented Generation", ["Random Answer Generator", "Recurrent Attention Graph", "Rapid AI Gateway"]),
        ("A hallucination in an LLM is...", "confident but incorrect output", ["a GPU error", "a slow response", "a blurry image"]),
        ("Prompt engineering is...", "designing inputs to get better model outputs", ["training a model from scratch", "compressing models", "writing SQL"]),
    ],
    "LLMs": [
        ("Tokens in an LLM are...", "pieces of text the model processes", ["passwords", "GPU cores", "API keys only"]),
        ("The context window is...", "the maximum tokens the model can consider at once", ["the training dataset size", "the number of GPUs", "the response latency"]),
        ("Sampling temperature controls...", "how random the output is", ["the model size", "the training speed", "the token price"]),
    ],
    "CI/CD": [
        ("Continuous integration means...", "merging and testing code frequently and automatically", ["deploying once a year", "manual QA only", "editing production directly"]),
        ("A pipeline stage that runs unit tests belongs to...", "CI", ["DNS", "IAM", "CDN"]),
        ("GitHub Actions workflows are configured in...", "YAML files under .github/workflows", ["package.json", "a Dockerfile only", "README.md"]),
    ],
    "Microservices": [
        ("A well-designed microservice should...", "own one business capability and deploy independently", ["share one table with every other service", "run inside a single process", "never use APIs"]),
        ("An API gateway...", "routes and secures client requests to services", ["stores the data", "compiles the code", "trains the models"]),
        ("A common downside of microservices is...", "distributed-system complexity", ["they cannot scale", "they allow one language only", "they cannot be tested"]),
    ],
    "REST APIs": [
        ("Which HTTP method replaces a resource and is idempotent?", "PUT", ["POST", "PATCH", "CONNECT"]),
        ("Which status code means a resource was created?", "201", ["200", "404", "500"]),
        ("REST resources are identified by...", "URLs", ["port numbers", "cookies", "headers only"]),
    ],
}


def level_label(pct: float) -> str:
    return "Strong" if pct >= 80 else "Developing" if pct >= 50 else "Needs work"


def get_quiz(skills: list[str], per_skill: int = 3) -> list[dict]:
    """Quiz items with deterministically shuffled options (same quiz on every rerun)."""
    quiz = []
    for skill in skills:
        for i, (q, correct, wrong) in enumerate(QUESTIONS.get(skill, [])[:per_skill]):
            opts = [correct] + list(wrong)
            random.Random(f"{skill}:{i}").shuffle(opts)
            quiz.append({"id": f"{skill}:{i}", "skill": skill, "question": q, "options": opts, "answer": correct})
    return quiz


def grade(quiz: list[dict], answers: dict[str, str]) -> dict[str, dict]:
    """answers maps quiz id -> chosen option text; unanswered counts as wrong."""
    results: dict[str, dict] = {}
    for item in quiz:
        r = results.setdefault(item["skill"], {"correct": 0, "total": 0})
        r["total"] += 1
        r["correct"] += int(answers.get(item["id"]) == item["answer"])
    return results


def merge_assessments(existing: dict, results: dict, today: str) -> dict:
    """The latest attempt for a skill replaces the earlier one."""
    merged = {k: dict(v) for k, v in existing.items()}
    for skill, r in results.items():
        merged[skill] = {"correct": r["correct"], "total": r["total"], "date": today}
    return merged
