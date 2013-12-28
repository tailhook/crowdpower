#!/bin/sh

mkdir run run/redis 2> /dev/null || true

exec bossrun
