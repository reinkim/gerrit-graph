# gerrit-graph

Generates graph for # of remaining review in certain projects.

Utilizes gerrit RESTful API. (You may need to upgrade gerrit to use this
script)

## Usage

Specify host-address project-name and output-filename (.svg) to script.
Statistics range may be narrowed by giving _--since_ argument.

eg:

    /gerrit-graph.py --host https://android-review.googlesource.com \
		             --project platform/sdk \
					 --since 2012-01-01 \
					 --out stats-android-platform_sdk.svg
