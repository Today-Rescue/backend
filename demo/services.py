from django.core.management import call_command


def reset_demo():
    call_command("seed_demo")
