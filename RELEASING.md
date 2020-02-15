# Release Procedure


To release a version ``MAJOR.MINOR.PATCH``, follow these steps:


 - [ ] Run all tests using `tox -pall`

   Ensure your are updated and in a clean working tree.

 - [ ] After all tests pass, bump the version in `setup.py` and `_version.py` 
    and commit the changes

 - [ ] Create a distribution and check it

        python setup.py sdist bdist_wheel
        twine check dist/*

 - [ ] Release to Pypy

        twine upload dist/* 

 - [ ] Tag the release commit and push it:

        git tag -a MAJOR.MINOR.PATCH 
        git push
        git push --tags

 - [ ] Test that it can be installed with `pip install`
 