# Welcome to tpudiepie!

`tpudiepie` (or `pu` for short) is a Python library and command-line
program for managing TPUs.

## Examples

### Watching your TPUs

`pu list` shows your TPUs.

![image](https://user-images.githubusercontent.com/59632/84264053-622b9200-aad5-11ea-9a8d-9bd8c78c856b.png)

If your TPU's name ends with a number, that's its `INDEX`. Rather than
specifying the full name of the TPU, you can refer to the TPU by its
`INDEX` on the command line. If two TPUs have the same index, an error
is thrown if you attempt to refer to either of them by `INDEX` (since
it would be ambiguous).

### Watching your TPUs continuously

`pu top` is like `htop` for TPUs. Every few seconds, it clears the
screen and runs `pu list`, i.e. it shows you the current status of all
your TPUs. Use Ctrl-C to quit.

### Babysitting a preemptible TPU

`pu babysit <TPU>` will watch the specified TPU. If it preempts, it
recreates the TPU automatically. You can specify commands to be run
once the TPU has been recreated (and its health is `HEALTHY`) by
passing by passing `-c <command>`. To run multiple commands, pass
multiple `-c <command>` options.

In a terminal, simulate a training session:
```sh
while true
do
  bash -c 'echo My Training Session; sleep 10000'
  echo restarted
  sleep 1
done
```

In a separate terminal, babysit a TPU. Whenever the TPU preempts,
this command does the following:

- recreates the TPU
- waits for the TPU's health to become `HEALTHY`
- kills our simulated training session

```sh
pu babysit my-tpu -c 'pkill -9 -f "My Training Session"'
```

You'll notice the simulated training session prints "restarted",
indicating that the kill was successful and the training process was
restarted.

In a real-world scenario, be sure that the pkill command only kills
one specific instance of your training script. For example, if
you run multiple training sessions with a script named `train.py`
using different `TPU_NAME` environment vars, a naive `pkill` command
like `pkill -f train.py` would kill both training sessions, rather
than the one associated with the TPU. 

(To solve that, I normally pass the TPU name as a command-line
argument, then run `pkill -9 -f <TPU>`.)

Also, be sure to pass `pkill -9` rather than `pkill`. That way, your
training session will be restarted even if it's frozen.

### Recreating a TPU

`pu recreate <TPU>` recreates an existing TPU, then waits for the
TPU's health to become `HEALTHY`. You can run commands after the TPU
is successfully recreated by passing `-c <command>`. To run multiple
commands, pass multiple `-c <command>` options.

```sh
# Recreate a TPU named foo
pu recreate foo
```

```sh
# Recreate a TPU named foo, but only if it's PREEMPTED. Don't prompt
for confirmation. Run a comand after recreating.
pu recreate foo --preempted --yes -c 'echo This only runs after recreating'
```

```sh
# `pu babysit foo` is roughly equivalent to the following. (The -c
# options are provided here for illustration purposes; you can pass
# those to `pu babysit` as well.)
while true
do
  pu recreate foo --preempted --yes \
   -c "echo TPU recreated. >> logs.txt" \
   -c "pkill -9 -f my_training_program.py"
  sleep 30
done
```

### Listing TPUs

`pu list` shows the current status of all your TPUs. You can use
`-t/--tpu <TPU>` to print the status of one specific TPU. To print the
status of multiple TPUs, pass multiple `-t <TPU>` options.

```sh
# List TPU named foo. If it doesn't exist, throw an error.
pu list -t foo
```

```sh
# Dump the TPU in json format. If it doesn't exist, throw an error.
pu list -t foo --format json
```

```sh
# List TPUs named foo or bar. If foo or bar don't exist, don't throw an
# error. For each TPU, print a line of JSON. Then use `jq` to extract
# some interesting subfields, and format the result using `column`.
pu list -t foo -t bar -s --format json | \
     jq ".name+\" \"+.state+\" \"+(.health//\"UNKNOWN\")" -c -r | column -t
```

## Commands

### `pu babysit`

```
Usage: tpudiepie babysit [OPTIONS] TPU

  Checks TPU every INTERVAL seconds. Recreates the TPU if (and only if) the
  tpu has preempted.

Options:
  --zone [asia-east1-c|europe-west4-a|us-central1-a|us-central1-b|us-central1-c|us-central1-f]
  --dry-run
  -i, --interval <seconds>        How often to check the TPU. (default: 30
                                  seconds)

  -c, --command TEXT              After the TPU has been recreated and is
                                  HEALTHY, run this command. (Useful for
                                  killing a training session after the TPU has
                                  been recreated.)

  --help                          Show this message and exit.
```

### `pu recreate`

```
Usage: tpudiepie recreate [OPTIONS] TPU

  Recreates a TPU, optionally switching the system software to the specified
  TF_VERSION.

Options:
  --zone [asia-east1-c|europe-west4-a|us-central1-a|us-central1-b|us-central1-c|us-central1-f]
  --version <TF_VERSION>          By default, the TPU is recreated with the
                                  same system software version.You can set
                                  this to use a specific version, e.g.
                                  `nightly`.

  -y, --yes
  --dry-run
  -p, --preempted                 Only recreate TPU if it has
                                  preempted. (Specifically, if the tpu's STATE
                                  is "PREEMPTED",proceed; otherwise do
                                  nothing.)

  -c, --command TEXT              After the TPU is HEALTHY, run this
                                  command. (Useful for killing a training
                                  session after the TPU has been recreated.)

  --help                          Show this message and exit.
```

### `pu list`

```
Usage: tpudiepie list [OPTIONS]

  List TPUs.

Options:
  --zone [asia-east1-c|europe-west4-a|us-central1-a|us-central1-b|us-central1-c|us-central1-f]
  --format [text|json]
  -c, --color / -nc, --no-color
  -t, --tpu TEXT                  List a specific TPU by id.
  -s, --silent                    If listing a specific TPU by ID, and there
                                  is no such TPU, don't throw an error.

  --help                          Show this message and exit.
```

### `pu reimage`

```
Usage: tpudiepie reimage [OPTIONS] TPU

  Reimages the OS on a TPU.

Options:
  --zone [asia-east1-c|europe-west4-a|us-central1-a|us-central1-b|us-central1-c|us-central1-f]
  --version <TF_VERSION>          By default, the TPU is reimaged with the
                                  same system software version. (This is handy
                                  as a quick way to reboot a TPU, freeing up
                                  all memory.)You can set this to use a
                                  specific version, e.g. `nightly`.

  -y, --yes
  --dry-run
  --help                          Show this message and exit.
```
