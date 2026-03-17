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
    'functions',
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
    r'^\/?\*\s*(' + '|'.join(DESCRIPTION_STOP_LABELS) + r')\s*:',
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
/*******************************************************************/
/*    PROGRAM NAME   : ISWKSHET                                    */
/*    LOCATION       : ees/system/source/screens                   */
/*    FUNCTION       : THIS PROGRAM MODULE GENERATES THE INTERVIEW */
/*                     OUTLIER WORKSHEETS.  IT ALSO CREATES AN OS  */
/*                     DATASET OF OUTLIER IDS FOR DCES USE.        */
/*                                                                 */
/*    DATE INSTALLED : 6/9/87                                      */
/*    WRITTEN BY     : MARY JO ANTHONY                             */
/*    MODIFICATIONS  : DATE - 4/13/88                              */
/*                     REASON - ADDITION OF FORMATED VALUES FOR    */
/*                              CODED VARIABLES AND ADDITION OF    */
/*                              SEQNO.                             */
/*                     BY - PETER KNAPP                            */
/*                     DATE - 6/15/88                              */
/*                     REASON - CORRECTION TO SEQNO.               */
/*                     BY - PETER KNAPP                            */
/*                     DATE - 7/15/88                              */
/*                     REASON - ADDITION OF FIL_RECT TO ALLTYPES   */
/*                              MEMBER OF SASOUT.                  */
/*                     BY - PETER KNAPP                            */
/*                     DATE - 8/8/88                               */
/*                     REASON - ADDITION OF &SUBSCRPT AS UPPER     */
/*                              LIMIT OF ARRAYS.                   */
/*                     BY - PETER KNAPP                            */
/*                     DATE - 10/19/88                             */
/*                     REASON - ADDITION OF EXT_TEST AND PINDX     */
/*                              TO ALLTYPES MEMBER OF SASOUT.      */
/*                     BY - PETER KNAPP                            */
/*1/24/92 - GOETTELMANN - CHANGES DUE TO FORMS REDESIGN - FORMAT   */
/*12/22/92  GOETTELMANN - ADDED REG_OFF TO OUTLIER SUMMARY REPORT  */
/*          MEMO 9/15/92 FROM J RYAN                               */
/*                     DATE - 11/02/93                             */
/*                     REASON - Q933 CHANGES -  MOVED   $RECORDR   */
/*                              TO &YDVGEH.SAS<Y> FORMAT LIBRARY.  */
/*                              PROC FORMAT, AND ADDED FMLY        */
/*                              VARIABLES CHDOTHX AND ALIOTHX IN   */
/*                              PLACE OF INCCONTX.                 */
/*                     BY - CHELSEA BROWN                          */
/*                     DATE - 03/17/94                             */
/*                     REASON - QUESTIONNAIRE CHANGES FOR 1994 -   */
/*                              VARIABLE QPREVOCC IS REPLACED BY   */
/*                              OCCUCODE, AND FORMAT $OCC IS       */
/*                              REPLACED BY $OCC941.               */
/*                     BY - CHELSEA BROWN                          */
/*02/01/96 - RAY JOU - ON REPORTS OF OUTLIER WORKSHEET AND OUTLIER */
/*                     SUMMARY REPORT, THE BREAKDOWN COMPONENTS OF */
/*                     THE CENSID WAS BEEN CHANGED TO A SINGLE 21  */
/*                     DIGIT NUMBER WITH NO BREAKS.  THIS CHANGE   */
/*                     EFFECT ON YEAR/QTR 954. 11/27/95 MEMO FROM  */
/*                     MARY F. PARRAN                              */
/*7/23/96 D GRIFFIN CREATE CENSID90 FOR Q961 OLD PROCESSING        */
/* 01/31/97 JAMES MODIFIED CODE FOR Q961 NEW PROCESSING            */
/*  CREATE CENSID THAT DOES NOT INCLUDE AREACD96 AND SERIAL96 Q961 */
/*06/10/98  X. GU MODIFY CODE TO MEET 5 DIGITAL QUARTERS         */
/*11/03/99 - D GRIFFIN-TEMPORARY FIX PROC RAPSAS OF PRIOR QUARTER  */
/*                     DATABASES IN MACRO CONTROL FOR RECTYPE XPB  */
/*                     IN Q992, Q993, Q994 PROCESSING.             */
/*06/04/2001 - STELLA HUNG - 2001 FORMS CHANGES.                   */
/*                     OLD SOURCE MODULE 'ISWKSHET'.               */
/*                     NEW BRACKET MEDIAN FIELDS ARE ADDED.        */
/*                     FILE EXTALLA IS CREATED FOR Q012/Q014.      */
/*                     FILE EXTALLA IS SAME AS FILE EXTALL, EXCEPT */
/*                     THAT FILE EXTALLA DOES NOT INCLUDE THOSE    */
/*                     NEW VARIABLES DUE TO 2001 FORMS CHANGES.    */
/*04/29/2002 - STELLA HUNG - DOWNSIZE FROM MAINFRAME TO UNIX.      */
/*                     COMBINE TWO SOURCE MODULES 'ISWKSHET' AND   */
/*                     'ISWKSH01' INTO ONE SOURCE MODULE 'ISWKSHET'*/
/*                     MODIFY CODES TO EXTRACT FOR NEEDED VARIABLES*/
/*                     FROM PREVIOUS THREE QUARTERS OF FMLY, MEMB  */
/*                     & EXPN DATABASES; VARIABLES USED TO BE      */
/*                     PASSED AS MACRO VARIABLES LISTS, BUT NOW IS */
/*                     PASSED AS RECORDS IN SAS DATA SET EXTALL.   */
/*                     DELETE CODES BEFORE QUARTER 19961.  CHANGE  */
/*                     RAPSAS TO SYBSAS.  OUTLIER WORK SHEETS AND  */
/*                     SUMMARY REPORTS WILL BE PRINTED ON XEROX    */
/*                     PRINTER.  ADD OPTIONS PRINT LINESLEFT TO    */
/*                     REMOVE EXTRA BLANK PAGE.                    */
/*09/19/2002 - STELLA HUNG - ADD 'LENGTH VAR_NAME $8' STATEMENT    */
/*                     FOR DATA SET OUTLIERS.                      */
/*08/22/2003 - J SHAPIRO - ADDED Z_SCORE TO OUTLIER REPORT. ADDED  */
/*                     LINESIZE=138 TO FILE WRKSHT PARAMETERS.     */
/*                     BEGINNING IN 20032: ALL NOTES (FROM THE NOTE*/
/*                     TABLE) PRESENT FOR A GIVEN  KEY  FILE-      */
/*                     RECTYPE COMBINATION WILL PRINT IMMEDIATELY  */
/*                     AFTER THE DESCRIPTION OF EACH OUTLIER       */
/*                     VARIABLE IDENTIFIED BY THAT COMBINATION OF  */
/*                      KEY  FILE-RECTYPE -- PROVIDED: EVERY LINE  */
/*                     OF EVERY NOTE MUST SATISFY A SERIES OF      */
/*                     CONDITIONS TO PRINT. IT IS POSSIBLE, WITHIN */
/*                     A GIVEN  KEY  FILE-RECTYPE COMBINATION, FOR */
/*                     INDIVIDUAL NOTE LINES TO PRINT FOR ONE      */
/*                     OUTLIER VARIABLE, BUT NOT FOR ANOTHER.      */
/*02/12/2004 - J SHAPIRO - INCREASED CNSFLG VARIABLE LENGTH FROM 2 */
/*                     TO 4. FOR FILE WRKSHT, SET LINESIZE=140.    */
/*                     BEGINNING IN 20032: ALL NOTES (FROM THE NOTE*/
/*                     TABLE) PRESENT FOR A GIVEN  KEY  FILE-      */
/*                     RECTYPE COMBINATION THAT SATISFY CERTAIN    */
/*                     CRITERIA WILL PRINT AFTER ALL OTHER SECTIONS*/
/*                     PRESENT, FOR EACH MATCHED OUTLIER           */
/*                     OBSERVATION. IT IS POSSIBLE, WITHIN A GIVEN */
/*                      KEY  FILE-RECTYPE COMBINATION, FOR         */
/*                     INDIVIDUAL NOTE LINES TO PRINT FOR ONE      */
/*                     OUTLIER VARIABLE, BUT NOT FOR ANOTHER.      */
/*09/17/2004 - J SHAPIRO - MODIFIED MACRO ISWKSHET TO ADD FMLY     */
/*                     VARIABLE  KEY  TO OUTLIER SUMMARY REPORT AND*/
/*                     FMLY VARIABLE FPRIMARY TO OUTLIER WORKSHEET */
/*                     REPORT.                                     */
/* 03/22/2005 - STELLA HUNG - 2005 SAMPLE REDESIGN CHANGES         */
/*            1. FOR 2005Q1 PROCESSING OF THE 2000 SAMPLE DESIGN   */
/*               AND FUTURE PROCESSSING QUARTERS, THE FORMAT OF THE*/
/*               PSU VARIABLE WILL UTILIZE THE UPDATED PHASE 3     */
/*               PRODUCTION FORMAT ENTITLED $PSU00DG REFLECTING THE*/
/*               2000 SAMPLE DESIGN.                               */
/*            2. FOR 2004Q4 AND PRIOR QUARTERS, AND FOR 2005Q1     */
/*               PROCESSING OF THE 1990 SAMPLE DESIGN, THE CURRENT */
/*               FORMAT OF THE PSU VARIABLE WILL BE RETAINED       */
/*               (UTILIZING THE $PSU FORMAT).                      */
/*09/15/2005 - J SHAPIRO - 2005 FORM CHANGES:                      */
/*                     ON THE PRINTED REPORT, "INTERVIEW OUTLIER   */
/*                     WORK SHEET", SHIFTED DISPLAYING  KEY  AND   */
/*                     FPRIMARY TEN SPACES TO THE RIGHT.           */
/*07/23/2009 - B. BEVERLY - REMOVED OVERPRINT STATEMENTS AND ADDED */
/*                          DASHES FOR COLUMN HEADERS. THIS WAS    */
/*                          DONE IN SUPPORT OF SCR 392 - TO RE-    */
/*                          DIRECT THE INTERVIEW SUMMARY AND WORK  */
/*                          SHEET REPORTS FROM THE PRINTER TO PDFS.*/
/*                          ALSO CHANGED THE LINESIZE TO 150 FOR   */
/*                          THE WORKSHEET PDF REPORT LISTING AND   */
/*                          CHANGED THE FILE STATEMENTS TO MATCH   */
/*                          THE I2A FILENAME STATEMENTS; THE OLD   */
/*                          FILENAMES WERE 'SUMREP' AND 'WRKSHT' - */
/*                          THE NEW NAMES ARE SUM AND WKS.         */
/* 01/26/2012 - THUY SHIPP -FIX WARNING MESSAGE FOR SAS 9.2        */
/*                          IMPLEMENTATION                         */
/* 07/24/2013 - M.KALAVAPUDI- 2013 FORM CHANGES                    */
/*              CONDITIONALLY REMOVED DROPPED VARIABELS IN 2013Q2. */
/*              REARRANGED WORK SHEET BECAUSE OF DELETED VARIABLES.*/
/*              MODIFIED CODE WITH REPLACED VARIABLES.             */
/* 01/04/2015 - R LEVY-       2015 CHANGES                         */
/*              CODE HAS BEEN MODIFIED TO ACCEPT NEWID AS THE      */
/*              PRIMARY KEY FOR 20151 AND BEYOND, FAMID IS USED FOR*/
/*              OLD AND CONTINUING CU'S.                           */
/* 09/27/2016 - V DRAGUNSKY - CODE CLEAN-UP.                       */
/*              CONDITIONAL CODE RELEVANT TO PRE-2015Q1 PROCESSING */
/*              REMOVED. &GBNEWID REFERENCES REPLACED WITH NEWID.  */
/*              &GBCTRLNO REFERENCES REPLACED WITH CTRLNO.         */
/*              INTERNAL MACRO DEFINITIONS PUT_F1, PUT_F2 DELETED  */
/*              BECAUSE THESE MACROS ARE NOT USED AFTER 2013Q2.    */
/*******************************************************************/
    """

    lines = text.split("\n")
    print(extract_description(lines))