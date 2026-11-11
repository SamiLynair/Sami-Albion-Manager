if __name__ == "__main__":
    import sys

    # The updater runs in an independent copy of the old executable, without
    # starting Qt or opening a second application window.
    from samialbion.updater import maybe_run_update_helper

    if not maybe_run_update_helper(sys.argv[1:]):
        from samialbion.ui_calculator import main

        main()
