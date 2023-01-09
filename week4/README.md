# Week4 Solution

## Run code

```
git clone git@github.com:Adg0/bootcamp.git
cd week4
python helper.py
```

## Visualize contract

To see the flow of execution visually install `XDOT` on linux. As the command below.

```
sudo apt install xdot
xdg-open cfg.dot
```

## Explanation

This is a voting app simulation.

3 accounts are generated for testing.

An ASA with unit-name `ENB` is needed for voting, minimum of `1000 uints`.

Voting choices are only `yes`, `no` or `abstain`.

Votes are valued based on `ENB` tokens held in voters account.
