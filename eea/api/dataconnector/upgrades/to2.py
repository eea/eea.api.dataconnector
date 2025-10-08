""" upgrade to 2.0 """


def run_upgrade(setup_context):
    """run upgrade to 2.0"""

    setup_context.runImportStepFromProfile(
        "profile-eea.api.dataconnector:default",
        "typeinfo",
        run_dependencies=False,
        purge_old=False,
    )
