# Week4 Solution

## Run code

```console
$ git clone git@github.com:Adg0/bootcamp.git
$ mv .env.example .env
$ vim .env
// Replace MNEMONIC value with your mnemonic
$ cd week4
$ pip install -r requirements.txt
$ python helper.py
```

## Visualize contract

To see the flow of TEAL execution visually install and run `XDOT` on linux. As the command below.

```console
$ sudo apt install xdot
$ xdg-open cfg.dot
```

The visual output is generated with [`tealer`](https://github.com/crytic/tealer).

## Explanation

This is a voting app simulation.

3 accounts are generated for testing. And funded by the an account on testnet, each with 1 algo.

An ASA with unit-name `ENB` is needed for voting, minimum of `1000 uints`.

Voting choices are only `yes`, `no` or `abstain`.

Votes are valued based on `ENB` tokens held in voters account.
