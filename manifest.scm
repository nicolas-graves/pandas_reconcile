(use-modules (guix packages)
             (guix download)
             (guix git-download)
             ((guix licenses) #:prefix license:)
             (gnu packages python)
             (gnu packages python-science)
             (gnu packages python-web)
             (gnu packages python-xyz)
             (gnu packages check)
             (guix build-system pyproject)
             (guix build-system python))

(packages->manifest
 (cons*
  (package
    (name "python-treelib")
    (version "1.7.0")
    (source
     (local-file "lib/treelib" "python-treelib"
                 #:recursive? #t
                 #:select? (git-predicate (string-append
                                           (dirname (current-filename))
                                           "/lib/treelib"))))
    (build-system pyproject-build-system)
    (propagated-inputs (list python-six))
    (home-page "https://github.com/caesar0301/treelib")
    (synopsis "Implementation of a tree structure in Python")
    (description
     "This package provides a Python implementation of a tree structure.")
    (license license:asl2.0))
  (specifications->packages
   '("python-mypy"
     "python-pandas"
     "python-pytest"
     "python-toolz"
     "python-wrapper"
     "which"))))
