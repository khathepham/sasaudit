import re
from typing import List


ORACLE_CONNECT_PATTERN = re.compile(r'connect\s+to\s+oracle', re.IGNORECASE)
ORACLE_LIBNAME_PATTERN = re.compile(r'libname\s+\w+\s+oracle\s+.*', re.IGNORECASE)
BLOCK_COMMENT_INLINE_PATTERN = re.compile(r'/\*.*?\*/', re.DOTALL)


# Labels that trigger description extraction when found in a * comment line.
# Add new labels here as needed — spaces before the colon are handled automatically.
DESCRIPTION_START_LABELS = [
    'description',
    'function',
    'purpose',
]

# Labels that mark the start of a new section, stopping extraction.
# Add new labels here as needed — spaces before the colon are handled automatically.
DESCRIPTION_STOP_LABELS = [
    'input parameters?',
    'output',
    'job_options',
    'notes?',
    'author',
    'date',
    'program',
    'date installed',
    'written by',
    'modifications',
]

# Compiled from the lists above — \s* between the label word(s) and colon
# handles formatting like "Purpose    :" or "Description:".
_START_LABEL_RE = re.compile(
    r'(' + '|'.join(DESCRIPTION_START_LABELS) + r')\s*:',
    re.IGNORECASE,
)
_STOP_LABEL_RE = re.compile(
    r'^\*\s*(' + '|'.join(DESCRIPTION_STOP_LABELS) + r')\s*:',
    re.IGNORECASE,
)

NO_DESCRIPTION = 'No description found'



def extract_description(lines: List[str]) -> str:
    """Extract the program description from a SAS file's header comment block.

    Searches for any start label (Description, Function, Purpose, etc.) inside a
    SAS * comment line. Spaces between the label and colon are ignored, so both
    'Description:' and 'Purpose    :' are matched correctly.

    Extraction continues across continuation comment lines and stops when a new
    section label (e.g. 'Input Parameters:', 'Output:') or a non-comment line
    is reached. Returns a single space-joined string, or NO_DESCRIPTION if none
    is found.

    To support additional start or stop labels, update DESCRIPTION_START_LABELS
    or DESCRIPTION_STOP_LABELS at the top of this file.
    """
    description_parts = []
    in_description = False

    for line in lines:
        stripped = line.strip()

        # Look for any recognised start label inside a * comment line.
        if not in_description:
            if stripped.startswith(('*', '/*')) and _START_LABEL_RE.search(stripped):
                in_description = True
                # Grab any text that follows the label on the same line.
                after_label = _START_LABEL_RE.split(stripped, maxsplit=1)[-1]
                text = _clean_comment_line(after_label)
                if text:
                    description_parts.append(text)
            continue


        # We are inside the description block — decide whether to keep going.
        if not stripped:
            continue  # Skip blank lines within the block.

        if not stripped.startswith(('*', '/*')):
            break  # Non-comment line — end of header block.

        if _STOP_LABEL_RE.match(stripped):
            break  # New section label encountered.

        text = _clean_comment_line(stripped)
        if text:
            description_parts.append(text)

    if not description_parts:
        return NO_DESCRIPTION

    return ' '.join(description_parts)

def _clean_comment_line(text: str) -> str:
    """Strip leading/trailing * characters and whitespace from a SAS comment line."""
    # Remove leading * and trailing * (with optional trailing semicolon).
    text = re.sub(r'^[\/?\*]+', '', text)
    text = re.sub(r'\*+;?\/?\s*$', '', text)
    return text.strip()


if __name__ == "__main__":
    text = """
    /*****************************************************************************/
    /*  PROGRAM NAME:   BBEDRIV (BRACKET EDIT)                                   */
    /*  LOCATION: ies/system/source                                              */
    /*  FUNCTION: CREATE UTILITY AND BRACKET EDIT FORMATS.                       */
    /*            REPLACE GENERIC VARIABLE NAME VALUES IN EDITDATA               */
    /*            FILE WITH FINC & MINC VARIABLE NAMES.                          */
    /*            ACCESS RAPID RELATION DATA VALUES.                             */
    /*            PERFORM CONSISTENCY EDIT AND BRACKET MEDIAN                    */
    /*            IMPUTATION ON EACH OBSERVATION IN THE EDITDATA FILE.           */
    /*            PRODUCE FREQUENCY TABLES FROM RESULTANT EDITDATA               */
    /*            FILE.                                                          */
    /*            UPDATE RAPID RELATION DATA BASE.                               */
    /*                                                                           */
    /*  DATE INSTALLED: 04/03/01                                                 */
    /*  WRITTEN BY: JULES SHAPIRO                                                */
    /*  MODIFICATIONS:                                                           */
    /*  DATE       - MODIFIED BY   -    REASON                                   */
    /*  08/04/2016   ALEXANDER NINH     LINUX MIGRATION - REMOVED PLATFORM       */
    /*  10/21/2016   KRIS'SHORNA        CHANGES FOR LEGACY CODE CLEANUP.         */
    /*  02/22/2017   MANJUSHA K         2017 CHANGES:                            */
    /*                                  MOVED %DOFORMAT TO IBUND3 HEADER.        */
    /*****************************************************************************/
    """

    lines = text.split("\n")
    print(extract_description(lines))