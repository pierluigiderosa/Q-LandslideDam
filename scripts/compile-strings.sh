#!/bin/bash
LRELEASE=$1
LOCALES=$2


for LOCALE in ${LOCALES}
do
    echo "Processing: ${LOCALE}.ts"
    if [ -n "${LRELEASE}" ] && command -v "${LRELEASE}" > /dev/null 2>&1
    then
        $LRELEASE i18n/${LOCALE}.ts
    else
        # lrelease not available: compile with the pure Python fallback
        python scripts/ts2qm.py i18n/${LOCALE}.ts
    fi
done
