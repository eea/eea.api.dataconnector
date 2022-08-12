
''' upgrade to 2.0 '''


def run_upgrade(setup_context):
    """ run upgrade to 2.0
    """

    setup_context.runImportStepFromProfile(
        "profile-eea.api.dataconnector:upgrade_2",
        "typeinfo",
        run_dependencies=False,
        purge_old=False,
    )