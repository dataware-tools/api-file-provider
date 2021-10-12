#!/usr/bin/env bash
#
# Generate OpenAPI Clients
#

set -e
set -x

usage() {

        cat <<EOUSAGE
-----------------------------------------------------------------
Usage: $0 <Schema URL> <Exported module name>
------------------------------------------------------------------
EOUSAGE
}

if [ $# -ne 2 ]; then
        usage
        exit 1
fi

URL=$1
EXPORTED_MODULE_NAME=$2

npm install

curl ${URL} -o ./schema.yaml

npx openapi-typescript-codegen --input ./schema.yaml --useOptions --output ./node/client --client node
npx openapi-typescript-codegen --input ./schema.yaml --useOptions --output ./browser/client

echo "export * as ${EXPORTED_MODULE_NAME} from \"./client\";" >./browser/index.ts
echo "export * as ${EXPORTED_MODULE_NAME} from \"./client\";" >./node/index.ts

npm run build
