# tpunicorn

`tpunicorn` (or `pu` for short) is a Python library and command-line
program for managing TPUs. For example, if you have a preemptible TPU
named `foo`, then `pu babysit foo` will recreate it automatically
whenever it preempts.

See [examples](#examples).

## Contact

- Twitter: [@theshawwn](https://twitter.com/theshawwn)
- HN: [sillysaurusx](https://news.ycombinator.com/item?id=23346972)
- Discord: [ML Community](#ml-community)
- Patreon: [thank you!](https://www.shawwn.com/thanks)

## Quickstart

```
# Install pu
sudo pip3 install -U tpunicorn
```

(Use `sudo pip3` at your own risk. It's potentially easier, since
`pu` is guaranteed to end up on your PATH regardless of your
platform, but see [installation caveats](#installation-caveats)
for a discussion of the tradeoffs.)

```
# View your TPUs
pu list

# Recreate a TPU named foo
pu recreate foo

# Watch a TPU named foo. If it preempts, recreate it automatically
pu babysit foo
```

Skip ahead to [examples](#examples) to see what else `pu` can do.

### Installation Caveats

- `pu` assumes you can successfully run
`gcloud compute tpus list`. If so, then you're done! Otherwise,
see the [Troubleshooting](#troubleshooting) section.

- Rather than `sudo pip3 install -U tpunicorn`, you can install
via a more "recommended" approach. (For example, the magic wormhole
project lists some
[reasons](https://magic-wormhole.readthedocs.io/en/latest/welcome.html#install-from-source)
you might want to avoid `sudo pip3`.)

Option 1: a local install
```
pip3 install --user -U tpunicorn
# add python's user directory to your PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
# restart your shell
exec -l $SHELL
# does pu work?
pu list
```

Option 2: a virtualenv
```
virtualenv venv
source venv/bin/activate
pip3 install tpunicorn
pu list
```

Unfortunately, you may experience a serious slowdown when using venv.
`pu` is implemented by shelling out to `gcloud compute tpus ...`, and
`gcloud` seems to be very unhappy when it's run inside of a
virtualenv. `gcloud compute tpus list` takes ~8 seconds for me, which
is a noticeable delay, and makes `pu list` quite uncomfortable to use.
I've attempted to debug this, but as far as I can tell, the slowdown
is somewhere deep inside of gcloud internals related to reconfiguring
paths. I assume it's detecting the venv and doing some sort of
reconfiguration to account for it.

## Examples

### Seeing your TPUs

`pu list` shows your TPUs.

![image](https://user-images.githubusercontent.com/59632/84264053-622b9200-aad5-11ea-9a8d-9bd8c78c856b.png)

The `INDEX` is determined by checking whether your TPU name ends with
a number. It's common to create TPUs named like `tpu1`, `tpu2`, etc.
If you use such a naming scheme, the number becomes its `INDEX` and
you can refer to the TPU by number via the command line, which is far
easier than typing out the whole name.

(If two TPUs have the same index, an error is thrown if you attempt to
refer to either of them by number, since that would be ambiguous.)

### Seeing your TPUs continuously

`pu top` is like `htop` for TPUs. Every few seconds, it clears the
screen and runs `pu list`, i.e. it shows you the current status of all
your TPUs. Use Ctrl-C to quit.

### Recreating a TPU

`pu recreate <TPU>` recreates an existing TPU, waits for the TPU's
health to become `HEALTHY`, then runs the commands specified via `-c
<command>`. To run multiple commands, pass multiple `-c <command>`
options.

```sh
# Recreate a TPU named foo
pu recreate foo
```

```sh
# Recreate a TPU named foo, but only if it's PREEMPTED. Don't prompt
# for confirmation. After the TPU recreates and is HEALTHY, run a
# command.
pu recreate foo --preempted --yes -c 'echo This only runs after the TPU is HEALTHY'
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

### Babysitting a preemptible TPU

`pu babysit <TPU>` will watch the specified TPU, recreating it
whenever it preempts. You can specify commands to run afterwards via
`-c <command>`. (For example, a command to kill your current training
session, or send you a message.) To run multiple commands, pass
multiple `-c <command>` options.

In a terminal, simulate a training session:
```sh
while true
do
  bash -c 'echo My Training Session; sleep 10000'
  echo restarting
  sleep 1
done
```

In a separate terminal, babysit a TPU named `my-tpu`:

```sh
pu babysit my-tpu -c 'pkill -9 -f "My Training Session"'
```
Whenever the TPU preempts, that command will:
- recreate the TPU named `my-tpu`
- wait for the TPU's health to become `HEALTHY`
- kill our simulated training session

The simulated training session will echo "restarting", indicating that
it was successfully killed and the training process restarted itself.

In a real-world scenario, be sure that the pkill command only kills
one specific instance of your training script. For example, if
you run multiple training sessions with a script named `train.py`
using different `TPU_NAME` environment vars, a naive `pkill` command
like `pkill -f train.py` would kill all of your training sessions,
rather than the one associated with the TPU. 

(To solve that, I normally pass the TPU name as a command-line
argument, then run `pkill -9 -f <TPU>`.)

Also, be sure to pass `pkill -9` rather than `pkill`. That way, your
training session will be restarted even if it's frozen.

Lastly, consider running your actual training script like so:

```
while true
do
  timeout --signal=SIGKILL 11h <your training command>
  echo restarting
  sleep 30
done
```

This will force-kill your training command after a maximum of 11 hours
of training (rather than waiting the theoretical maximum of 24 hours
before your TPU preempts). This way, if your training session freezes
for some reason (e.g. the TPUEstimator API stops making progress) then
you'll lose no more than a few hours of training time.

Without this, we kept running into situations like "wake up the next
day and discover that the training session has been frozen for the
last 12 hours." We're still not entirely sure why. Suffice to say,
if your training session takes an hour to get into a stable state,
you'll lose only ~2 hours in the usual case (no freezes; everything
normal) and gain several hours in the worst case (the training loop
froze and no one noticed).

You might feel tempted to put a `pu recreate $TPU_NAME -y` command
inside that while loop. After all, if your training session
terminates, shouldn't it recreate the TPU? Perhaps; feel free to try
it out and see if you like it. In our experience, we've found it's
more effective to [manage our TPUs separately](https://www.tensorfork.com/tpus)
rather than try to solve both concerns in the same script.

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
     jq '.name+" "+.state+" "+(.health//"UNKNOWN")' -c -r | column -t
```

## Commands

### `pu babysit`

```
Usage: tpunicorn babysit [OPTIONS] TPU

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
Usage: tpunicorn recreate [OPTIONS] TPU

  Recreates a TPU, optionally switching the system software to the specified
  TF_VERSION.

Options:
  --zone [asia-east1-c|europe-west4-a|us-central1-a|us-central1-b|us-central1-c|us-central1-f]
  --version <TF_VERSION>          By default, the TPU is recreated with the
                                  same system software version. You can set
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
Usage: tpunicorn list [OPTIONS]

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
Usage: tpunicorn reimage [OPTIONS] TPU

  Reimages the OS on a TPU.

Options:
  --zone [asia-east1-c|europe-west4-a|us-central1-a|us-central1-b|us-central1-c|us-central1-f]
  --version <TF_VERSION>          By default, the TPU is reimaged with the
                                  same system software version. (This is handy
                                  as a quick way to reboot a TPU, freeing up
                                  all memory.) You can set this to use a
                                  specific version, e.g. `nightly`.

  -y, --yes
  --dry-run
  --help                          Show this message and exit.
```

## Troubleshooting

1. Ensure your project is set

```
gcloud config set project <your-project-id>
```

Note that the project ID isn't necessarily the same as the project
name. You can get it via the GCE console:

![image](https://user-images.githubusercontent.com/59632/84266707-c94b4580-aad9-11ea-8615-3a00926633c4.png)

While you're there, go the [Cloud TPU](https://console.cloud.google.com/compute/tpus) page:

![image](https://user-images.githubusercontent.com/59632/84266949-2d6e0980-aada-11ea-81e6-939391fac8b0.png)

If it asks you to enable the Cloud TPU API, then do so. Afterwards you
should see the GCE TPU dashboard:

![image](https://user-images.githubusercontent.com/59632/84267077-5f7f6b80-aada-11ea-8590-a437f8dcc5e1.png)

Create a TPU using "Create TPU node" to verify that your project has
TPU quota in the desired region.

2. Ensure your command-line tools are properly authenticated

Use `gcloud auth list` to see your current account.

If security isn't a concern, you can use `gcloud auth login` followed
by `gcloud auth application-default login` to log in as your primary
Google identity. Usually, this means that your terminal now has "root
access" to all GCE resources.

If you're on a server, you might want to use a service account
instead.

- create a [service
  account](https://console.cloud.google.com/iam-admin/serviceaccounts),
  granting it the "TPU Admin" role for TPU management, or "TPU Viewer"
  role for read-only viewing. 

- [create a keyfile](https://cloud.google.com/iam/docs/creating-managing-service-account-keys#iam-service-account-keys-create-gcloud)

- Upload the keyfile to your server. (I use `wormhole send ~/keys.json`
  for that. You can install it with `pip install magic-wormhole`.)

- [activate your service account](https://cloud.google.com/sdk/gcloud/reference/auth/activate-service-account)

For example, I created a `tpu-test` service account, then created a
`~/tpu_key.json` keyfile:

```
$ gcloud iam service-accounts keys create ~/tpu_key.json --iam-account tpu-test@gpt-2-15b-poetry.iam.gserviceaccount.com
created key [03db745322b4e7c4e9e2036386d1e908eb2e1a52] of type [json] as [/Users/bb/tpu_key.json] for [tpu-test@gpt-2-15b-poetry.iam.gserviceaccount.com]
```

Then I sent that `~/tpu_key.json` file to my server, and activated the
service account:

```
$ gcloud auth activate-service-account tpu-test@gpt-2-15b-poetry.iam.gserviceaccount.com --key-file ~/tpu_key.json
Activated service account credentials for: [tpu-test@gpt-2-15b-poetry.iam.gserviceaccount.com]
```


I checked `gcloud auth list` to verify I'm now using that service
account:
```
$ gcloud auth list
                  Credentialed Accounts
ACTIVE  ACCOUNT
        shawnpresser@gmail.com
*       tpu-test@gpt-2-15b-poetry.iam.gserviceaccount.com

To set the active account, run:
    $ gcloud config set account `ACCOUNT`

```

At that point, as long as you've run `gcloud config set project <your-project-id>`,
then `gcloud compute tpus list --zone europe-west4-a` should be successful.

(To avoid having to pass `--zone europe-west4-a` to all your gcloud
commands, you can make it the default zone:

```
gcloud config set compute/zone europe-west4-a
```

As far as I know, it's completely safe to make a "TPU Viewer" service
account world-readable. For example, if you want to let everyone view
your TPUs [for some reason](https://www.tensorfork.com/tpus), you can
simply stick the `~/tpu_key.json` file somewhere that anyone can
download.

(If this is mistaken, please [DM me on twitter](https://twitter.com/theshawwn).)

## ML Community

If you're an ML enthusiast, join our [TPU Podcast Discord Server](https://discordapp.com/invite/x52Xz3y).
There are now ~400 members, with ~60 online at any given time:

![image](https://user-images.githubusercontent.com/59632/84269906-bc7d2080-aade-11ea-8b4e-f78412855d43.png)

There are a variety of interesting channels:

- `#papers` for pointing out interesting research papers
- `#research` for discussing ML research
- `#show` and `#samples` for showing off your work
- `#hardware` for hardware enthusiasts
- `#ideas` for brainstorming
- `#tensorflow` and `#pytorch`
- `#cats`, `#doggos`, and of course `#memes`
- A "bot zone" for interacting with our discord bots, such as using
  `!waifu red_hair blue_eyes` to generate an anime character using
  stylegan:
![image](https://user-images.githubusercontent.com/59632/84270613-cfdcbb80-aadf-11ea-9762-83b0c84d4cc6.png)
- Quite a few more.

## Support

*If you found this library helpful, consider [joining my patreon](https://www.shawwn.com/thanks).*
