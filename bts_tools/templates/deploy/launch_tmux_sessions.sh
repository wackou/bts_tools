#!/usr/bin/env bash

{%- for client in config_yaml['clients'] -%}
{% set client_type = config_yaml['clients'][client].get('type', client) %}

# tmux sessions for {{ client_type }} client
tmux new -d -s {{ client_type }}
tmux send -t {{ client_type }}.0 workon SPACE bts_tools ENTER
tmux send -t {{ client_type }}.0 {{ client_type }} SPACE run ENTER

tmux new -d -s {{ client_type }}_cli
tmux send -t {{ client_type }}_cli.0 workon SPACE bts_tools ENTER
tmux send -t {{ client_type }}_cli.0 {{ client_type }} SPACE run_cli

{%- endfor %}
