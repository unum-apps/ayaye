"""
Module for the Daemon
"""

# pylint: disable=no-self-use,too-many-instance-attributes

import os
import time
import micro_logger
import json
import yaml

import openai

import redis

import relations_rest

import prometheus_client

import unum_base
import unum_ledger

PROCESS = prometheus_client.Gauge("process_seconds", "Time to complete a processing task")
FACTS = prometheus_client.Summary("facts_written", "Facts written")
ACTS = prometheus_client.Summary("acts_read", "Acts read")

WHO = "ayaye"
META = """
title: the Ay Aye (AI) App
description: ayaye interface with this Unum.
help: |
  Welcome to this ayaye App, how this Unum works with ChatGPT, etc.
channel: unum-ayaye
commands:
- name: ask
  description: Run a prompt and get an answer back.
  help: |
    Just sends what you type write to ChatGPT.

    You can take like a listing from some other command and feed that in here. Just type what you want it to do, ctrl-return for a new line, and paste in the listing.

    Just be careful. This costs money.
  requires: none
  examples:
  - meme: '?'
    args: Do you know what a Unifist is?
    description: Sees if this project knows what we are
  usages:
  - name: prompt
    meme: '?'
    description: Asks ChatGPT a general question
    args:
    - name: question
      description: The question
      format: remainder
"""
NAME = f"{WHO}-daemon"

class Daemon(unum_base.AppSource): # pylint: disable=too-few-public-methods
    """
    Daemon class
    """

    def __init__(self):

        self.name = self.group = NAME
        self.unifist = unum_ledger.Base.SOURCE
        self.group_id = os.environ["K8S_POD"]

        self.sleep = int(os.environ.get("SLEEP", 5))

        self.logger = micro_logger.getLogger(self.name)

        self.redis = redis.Redis(host=f'redis.{self.unifist}', encoding="utf-8", decode_responses=True)

        self.source = relations_rest.Source(self.unifist, url=f"http://api.{self.unifist}")

        with open("/opt/service/secret/openai.json", "r") as openai_file:
            self.openai = openai.Client(api_key = json.load(openai_file)["key"])

        self.app = unum_ledger.App.one(who=WHO).retrieve(False)

        if not self.app:
            self.app = self.journal_change("create", unum_ledger.App(who=WHO))

        self.journal_change("update", self.app, {"meta": yaml.safe_load(META)})

        if (
            not self.redis.exists("ledger/fact") or
            self.group not in [group["name"] for group in self.redis.xinfo_groups("ledger/fact")]
        ):
            self.redis.xgroup_create("ledger/fact", self.group, mkstream=True)

        if (
            not self.redis.exists("ledger/act") or
            self.group not in [group["name"] for group in self.redis.xinfo_groups("ledger/act")]
        ):
            self.redis.xgroup_create("ledger/act", self.group, mkstream=True)

    def command_ask(self, instance):
        """
        Perform the apps
        """

        question = instance["what"]["values"]["question"]

        metas = []

        for origin in unum_ledger.Origin.many(status="active"):
            metas.append(origin.meta)

        for app in unum_ledger.App.many(status="active"):
            metas.append(app.meta)

        response = self.openai.responses.create(
            model="gpt-4o",
            instructions="Just a general question",
            input=question
        )

        text = response.output_text

        self.create_act(
            entity_id=instance["what"]["entity_id"],
            app_id=self.app.id,
            when=int(time.time()),
            what={
                "base": "statement",
                "text": text,
                "ancestor": instance["what"]

            },
            meta={"ancestor": instance["meta"]}
        )

    def do_command(self, instance):
        """
        Perform the who
        """

        name = instance["what"]["command"]

        if name == "ask":
            self.command_ask(instance)

    @PROCESS.time()
    def process(self):
        """
        Reads people off the queue and logs them
        """

        message = self.redis.xreadgroup(self.group, self.group_id, {
            "ledger/fact": ">",
            "ledger/act": ">"
        }, count=1, block=1000*self.sleep)

        if not message:
            return

        elif "fact" in message[0][1][0][1]:

            instance = json.loads(message[0][1][0][1]["fact"])
            self.logger.info("fact", extra={"fact": instance})
            FACTS.observe(1)

            if (
                self.is_active(instance["what"].get("entity_id")) and
                not instance["what"].get("error") and
                not instance["what"].get("errors")
            ):

                if (
                    instance["what"].get("command") and
                    WHO in instance["what"].get("apps", [])
                ):
                    self.do_command(instance)

            self.redis.xack("ledger/fact", self.group, message[0][1][0][0])

        elif "act" in message[0][1][0][1]:

            instance = json.loads(message[0][1][0][1]["act"])
            self.logger.info("act", extra={"act": instance})
            ACTS.observe(1)

            if (
                self.is_active(instance["what"].get("entity_id")) and
                not instance["what"].get("error") and
                not instance["what"].get("errors")
            ):

                if (
                    instance["what"].get("command") and
                    WHO in instance["what"].get("apps", [])
                ):
                    self.do_command(instance)

            self.redis.xack("ledger/act", self.group, message[0][1][0][0])

    def run(self):
        """
        Main loop with sleep
        """

        prometheus_client.start_http_server(80)

        while True:

            self.process()
