"""Pornește homr (recunoașterea partiturilor) ca program separat; din el se face homr.exe în workflow-ul componente."""
import multiprocessing
import sys

if __name__ == '__main__':
    multiprocessing.freeze_support()
    if sys.stdout is None:
        import os
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = sys.stdout
    from homr.main import main
    main()
