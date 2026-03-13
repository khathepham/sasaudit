options mlogic mprint symbolgen;

proc printto log='C:\Users\Wiley_J\OneDrive - US Department of Labor - BLS\Desktop\test_case\output.txt' new;
run;

/*=============================================================================
  SAS Program Reference Exporter - Windows Compatible (Updated Version)
  
  Purpose: Scans SAS programs and extracts all references (libnames, macros,
           datasets, etc.) and exports to Excel with line counts
  
  Usage: %export_sas_references(
           input_dir=C:/path/to/sas/programs,
           output_file=C:/path/to/output.xlsx
         );
=============================================================================*/

%macro export_sas_references(input_dir=, output_file=sas_references.xlsx);

    /* Clean up any existing work datasets first */
    proc datasets library=work nolist;
        delete libname_refs macro_defs macro_calls dataset_refs 
               includes proc_usage sas_files file_line_counts sas_inventory;
    quit;

    /* Create output datasets with proper initialization */
    data libname_refs;
        length program $200 folder_path $500 libname $32 path $500 db_engine $20 source_type $20 line_num 8;
        call missing(of _all_);
        stop;
    run;

    data macro_defs;
        length program $200 folder_path $500 macro_name $32 line_num 8;
        call missing(of _all_);
        stop;
    run;

    data macro_calls;
        length program $200 folder_path $500 macro_name $32 line_num 8;
        call missing(of _all_);
        stop;
    run;

    data dataset_refs;
        length program $200 folder_path $500 library $32 dataset $32 ref_type $10 line_num 8;
        call missing(of _all_);
        stop;
    run;

    data includes;
        length program $200 folder_path $500 include_path $500;
        call missing(of _all_);
        stop;
    run;

    data proc_usage;
        length program $200 folder_path $500 proc_name $32 line_num 8;
        call missing(of _all_);
        stop;
    run;

    data file_line_counts;
        length program $200 folder_path $500 total_lines 8;
        call missing(of _all_);
        stop;
    run;

    data sas_inventory;
        length program $200 folder_path $500 path $500
               title $500 description $2000 owner $200
               created_date $30 last_modified_date $30
               app_category $30
               bls_cost_center $100 business_process $200
               location $200 data_col $200 gitlab $200
               cost_center_title $100 office_code $50
               office_title $100 item_type $50;
        call missing(of _all_);
        stop;
    run;

    /* Windows-compatible: Get list of all .sas files in directory */
    filename dirlist pipe "dir ""&input_dir\*.sas"" /s /b";
    
    data sas_files;
        length filepath $500 folder_path $500 program_name $200;
        infile dirlist truncover;
        input filepath $500.;
        
        /* Extract just the filename */
        program_name = scan(filepath, -1, '\');
        
        /* Extract the folder path (everything except the filename) */
        _last_slash = length(filepath) - length(program_name);
        folder_path = substr(filepath, 1, _last_slash - 1);
        
        /* Make folder path relative to input directory for cleaner display */
        folder_path = tranwrd(folder_path, "&input_dir", "");
        if folder_path = '' then folder_path = '[Root]';
        else if substr(folder_path, 1, 1) = '\' then folder_path = substr(folder_path, 2);
    run;

    filename dirlist clear;

    /* Count files found */
    proc sql noprint;
        select count(*) into :file_count trimmed from sas_files;
    quit;

    %put NOTE: Found &file_count SAS files to process;

    /* Create macro variable list of all files */
    proc sql noprint;
        select filepath, folder_path into :file1-:file9999, :folder1-:folder9999
        from sas_files;
    quit;

    /* Process each file using a loop instead of call execute */
    %do i = 1 %to &file_count;
        %let current_file = &&file&i;
        %let current_folder = &&folder&i;
        %parse_sas_file(&current_file, &current_folder);
    %end;

    %put NOTE: All files processed;

    /* Use directly counted line totals - accurate for ALL programs */
    proc sql;
        create table program_line_counts as
        select program, folder_path, total_lines
        from file_line_counts
        order by folder_path, program;
    quit;

    /* Remove duplicates from results */
    proc sort data=libname_refs nodupkey; by folder_path program libname source_type line_num; run;
    proc sort data=macro_defs nodupkey; by folder_path program macro_name line_num; run;
    proc sort data=macro_calls nodupkey; by folder_path program macro_name line_num; run;
    proc sort data=dataset_refs nodupkey; by folder_path program library dataset ref_type line_num; run;
    proc sort data=includes nodupkey; by folder_path program include_path; run;
    proc sort data=proc_usage nodupkey; by folder_path program proc_name line_num; run;
    proc sort data=sas_inventory nodupkey; by folder_path program; run;

    /* Create summary statistics */
    data summary_stats;
        length category $50 count 8;
        category = 'Total Programs Scanned'; count = &file_count; output;
    run;
    
    proc sql;
        insert into summary_stats
        select 'LIBNAME References' as category, count(*) as count from libname_refs;
        
        insert into summary_stats
        select 'Macro Definitions' as category, count(*) as count from macro_defs;
        
        insert into summary_stats
        select 'Macro Calls' as category, count(*) as count from macro_calls;
        
        insert into summary_stats
        select 'Dataset References' as category, count(*) as count from dataset_refs;
        
        insert into summary_stats
        select 'Include Statements' as category, count(*) as count from includes;
        
        insert into summary_stats
        select 'PROC Statements' as category, count(*) as count from proc_usage;
    quit;

    /* Export all results to Excel with multiple sheets */
    ods excel file="&output_file" 
              options(sheet_interval='proc' 
                      sheet_name='SAS_Inventory');

    proc print data=sas_inventory noobs label;
        title "SAS Program Inventory";
        title2 "Source Directory: &input_dir";
        label program            = "Program Name"
              folder_path        = "Folder Path"
              path               = "Path"
              title              = "Title"
              description        = "Description"
              owner              = "Owner"
              created_date       = "Program Creation Date"
              last_modified_date = "Last Modified Date"
              app_category       = "Application Category"
              bls_cost_center    = "BLS Cost Center"
              business_process   = "Business Process"
              location           = "Location"
              data_col           = "Data"
              gitlab             = "Gitlab"
              cost_center_title  = "BLS Cost Center: Cost Center Title"
              office_code        = "BLS Cost Center: Office Code"
              office_title       = "BLS Cost Center: Office Title"
              item_type          = "Item Type";
    run;

    ods excel options(sheet_name='Summary');
    
    proc print data=summary_stats noobs label;
        title "SAS Program Reference Summary";
        title2 "Source Directory: &input_dir";
        label category = "Category"
              count = "Count";
    run;

    ods excel options(sheet_name='Program_Line_Counts');
    proc print data=program_line_counts noobs label;
        title "Program Line Counts";
        label program = "Program Name"
              folder_path = "Folder Path"
              total_lines = "Total Lines of Code";
    run;

    ods excel options(sheet_name='Libname_References');
    proc print data=libname_refs noobs label;
        title "LIBNAME References";
        label program = "Program"
              folder_path = "Folder Path"
              libname = "Library Name"
              db_engine = "Engine/Type"
              path = "Path/Connection"
              source_type = "Source Type"
              line_num = "Line Number";
    run;

    ods excel options(sheet_name='Macro_Definitions');
    proc print data=macro_defs noobs label;
        title "Macro Definitions";
        label program = "Program"
              folder_path = "Folder Path"
              macro_name = "Macro Name"
              line_num = "Line Number";
    run;

    ods excel options(sheet_name='Macro_Calls');
    proc print data=macro_calls noobs label;
        title "Macro Calls";
        label program = "Program"
              folder_path = "Folder Path"
              macro_name = "Macro Name"
              line_num = "Line Number";
    run;

    ods excel options(sheet_name='Dataset_References');
    proc print data=dataset_refs noobs label;
        title "Dataset References";
        label program = "Program"
              folder_path = "Folder Path"
              library = "Library"
              dataset = "Dataset"
              ref_type = "Reference Type"
              line_num = "Line Number";
    run;

    ods excel options(sheet_name='Include_Statements');
    proc print data=includes noobs label;
        title "Include Statements";
        label program = "Program"
              folder_path = "Folder Path"
              include_path = "Include Path";
    run;

    ods excel options(sheet_name='PROC_Usage');
    proc print data=proc_usage noobs label;
        title "PROC Usage";
        label program = "Program"
              folder_path = "Folder Path"
              proc_name = "Procedure Name"
              line_num = "Line Number";
    run;

    ods excel close;

    %put ;
    %put NOTE: ============================================;
    %put NOTE: Excel file created: &output_file;
    %put NOTE: Total programs processed: &file_count;
    %put NOTE: Processing complete!;
    %put NOTE: ============================================;

%mend export_sas_references;


/* Macro to parse individual SAS file - DEFINED OUTSIDE main macro */
%macro parse_sas_file(filepath, folder_path);
    
    %local program_name filepath_quoted;
    %let filepath_quoted = %bquote(&filepath);
    %let program_name = %scan(&filepath_quoted, -1, \);
    
    %put NOTE: ========================================;
    %put NOTE: Processing: &program_name;
    %put NOTE: Folder: &folder_path;
    %put NOTE: Full path: &filepath_quoted;
    %put NOTE: ========================================;
    
    /* Check if file exists first */
    %if %sysfunc(fileexist(&filepath_quoted)) %then %do;

        /* Directly count all lines in the file (raw, before any filtering) */
        data _temp_count;
            length program $200 folder_path $500;
            retain total_lines 0;
            infile "&filepath_quoted" truncover end=eof lrecl=32767;
            input;
            total_lines + 1;
            program = "&program_name";
            folder_path = "&folder_path";
            if eof then output;
            keep program folder_path total_lines;
        run;

        proc append base=file_line_counts data=_temp_count force; run;

        /* Read the file directly without filename statement */
        data _temp_lines;
            length line $32767 program $200 folder_path $500 line_clean $32767;
            retain in_comment 0;
            
            infile "&filepath_quoted" truncover end=eof lrecl=32767;
            input line $32767.;
            program = "&program_name";
            folder_path = "&folder_path";
            line_num = _n_;

            %* Strip carriage returns - Windows CRLF defense ;
            line = compress(line, '0D'x);
            
            %* Work with a clean copy ;
            line_clean = strip(line);
            
            %* Handle multi-line comment blocks ;
            if in_comment then do;
                if index(line_clean, '*/') > 0 then do;
                    %* End of comment block - keep everything after the marker ;
                    in_comment = 0;
                    _pos = index(line_clean, '*/') + 2;
                    if _pos <= length(line_clean) then
                        line_clean = substr(line_clean, _pos);
                    else
                        line_clean = '';
                end;
                else do;
                    %* Still in comment, skip entire line ;
                    delete;
                end;
            end;
            
            %* Handle inline comments - multi-pass to catch ALL pairs ;
            if in_comment = 0 then do;

                %* Pass 1 - Strip macro-style comments ;
                do while(prxmatch('/%\*/', line_clean) > 0);
                    _start = prxmatch('/%\*/', line_clean);
                    _end_semi = index(substr(line_clean, _start), ';');
                    if _end_semi > 0 then do;
                        if _start > 1 then _before = substr(line_clean, 1, _start - 1);
                        else _before = '';
                        _after = substr(line_clean, _start + _end_semi);
                        line_clean = strip(_before || ' ' || _after);
                    end;
                    else do;
                        %* Macro comment runs to end of line - truncate ;
                        %* No leave needed - truncation exits the loop naturally ;
                        if _start > 1 then line_clean = substr(line_clean, 1, _start - 1);
                        else line_clean = '';
                    end;
                end;

                %* Pass 2 - Strip orphan close-comment markers before any open-comment ;
                do while(index(line_clean, '*/') > 0 and
                         (index(line_clean, '/*') = 0 or
                          index(line_clean, '*/') < index(line_clean, '/*')));
                    _end = index(line_clean, '*/');
                    if _end > 1 then _before = substr(line_clean, 1, _end - 1);
                    else _before = '';
                    _after = substr(line_clean, _end + 2);
                    line_clean = strip(_before || ' ' || _after);
                end;

                %* Pass 3 - Iteratively strip ALL complete comment pairs ;
                do while(index(line_clean, '/*') > 0);
                    _start = index(line_clean, '/*');
                    %* Search for close-comment only AFTER the open-comment ;
                    _after_open = substr(line_clean, _start + 2);
                    _end_rel = index(_after_open, '*/');
                    if _end_rel > 0 then do;
                        %* Complete pair found - strip it ;
                        if _start > 1 then _before = substr(line_clean, 1, _start - 1);
                        else _before = '';
                        _after = substr(line_clean, _start + 2 + _end_rel + 1);
                        line_clean = strip(_before || ' ' || _after);
                    end;
                    else do;
                        %* Unclosed open-comment - rest of line is a multi-line comment ;
                        %* No leave needed - truncation exits the loop naturally ;
                        in_comment = 1;
                        if _start > 1 then line_clean = substr(line_clean, 1, _start - 1);
                        else line_clean = '';
                    end;
                end;
            end;
            
            %* Final cleanup ;
            line_clean = strip(line_clean);
            
            %* Skip empty lines and star-style comments ;
            if line_clean = '' then delete;
            if length(line_clean) >= 1 and substr(line_clean, 1, 1) = '*' then delete;
            
            %* Use cleaned line for processing ;
            line = line_clean;
            line_upper = upcase(line);
            
            drop line_clean _start _end _before _after _pos _end_semi _after_open _end_rel;
        run;

        /* Extract LIBNAME statements */
        data _temp_libnames;
            length program $200 folder_path $500 libname $32 db_engine $20 path $500 source_type $20 line_num 8;
            set _temp_lines;
            
            /* Initialize to avoid issues */
            libname = '';
            db_engine = '';
            path = '';
            source_type = '';
            
            /* Case 1: Regular LIBNAME statement */
            if index(line_upper, 'LIBNAME ') > 0 then do;
                source_type = 'LIBNAME';
                
                _pos = index(line_upper, 'LIBNAME');
                _rest = substr(line, _pos + 7);
                
                libname = scan(_rest, 1, ' ');
                db_engine = scan(_rest, 2, ' ');
                
                _engine_pos = index(upcase(_rest), upcase(strip(db_engine)));
                if _engine_pos > 0 then do;
                    path = substr(_rest, _engine_pos + length(strip(db_engine)));
                    path = compress(path, '"' || "'" || ';');
                    path = strip(path);
                end;
                
                /* Only output valid libnames (not blank, not "LIBNAME", not "=") */
                /* Validate: SAS libnames are 1-8 chars, start with letter/underscore */
                if libname ne '' and libname ne 'LIBNAME' and libname ne '=' and 
                   length(strip(libname)) > 0 and length(strip(libname)) <= 8 and
                   prxmatch('/^[A-Za-z_][A-Za-z0-9_]*$/', strip(libname)) > 0 then output;
            end;
            
            /* Case 2: Macro parameter libnames (mLibname=, mLibrary=, mLib=, mSchema=) */
            /* Exclude lines with %let since those are assignments, not usage */
            if prxmatch('/\b(mLibname|mLibrary|mLib|mSchema|mDatabase)\s*=/i', line) > 0 
               and index(upcase(line), '%LET') = 0 then do;
                source_type = 'MACRO_PARAM';
                
                /* Initialize */
                _start = 0;
                
                /* Find the matching pattern - handle optional spaces */
                if prxmatch('/mLibname\s*=/i', line) > 0 then _start = prxmatch('/mLibname\s*=/i', line);
                else if prxmatch('/mLibrary\s*=/i', line) > 0 then _start = prxmatch('/mLibrary\s*=/i', line);
                else if prxmatch('/mLib\s*=/i', line) > 0 then _start = prxmatch('/mLib\s*=/i', line);
                else if prxmatch('/mSchema\s*=/i', line) > 0 then _start = prxmatch('/mSchema\s*=/i', line);
                else if prxmatch('/mDatabase\s*=/i', line) > 0 then _start = prxmatch('/mDatabase\s*=/i', line);
                
                if _start > 0 then do;
                    /* Get substring from the match position */
                    _rest = substr(line, _start);
                    
                    /* Find the equals sign (may have spaces before it) */
                    _equals_pos = index(_rest, '=');
                    if _equals_pos > 0 then do;
                        _after_equals = substr(_rest, _equals_pos + 1);
                        
                        /* Extract libname value (stop at space, comma, paren, or semicolon) */
                        libname = strip(scan(_after_equals, 1, ',);'));
                        libname = compress(libname, '"' || "'");
                        
                        db_engine = 'MACRO_PARAM';
                        path = 'Assigned via macro parameter';
                        
                        /* Validate libname format */
                        if libname ne '' and length(strip(libname)) > 0 and
                           length(strip(libname)) <= 8 and
                           prxmatch('/^[A-Za-z_][A-Za-z0-9_]*$/', strip(libname)) > 0 then output;
                    end;
                end;
            end;
            
            keep program folder_path libname db_engine path source_type line_num;
        run;

        proc append base=libname_refs data=_temp_libnames force; run;

        /* Extract MACRO definitions (%macro) */
        data _temp_macro_defs;
            set _temp_lines;
            length macro_name $32;
            
            if index(line_upper, '%MACRO') > 0 then do;
                _pos = index(line_upper, '%MACRO');
                _rest = substr(line, _pos + 6);
                macro_name = scan(_rest, 1, ' (;');
                if macro_name ne '' then output;
            end;
            keep program folder_path macro_name line_num;
        run;

        proc append base=macro_defs data=_temp_macro_defs force; run;

        /* Extract MACRO calls (%macroname) */
        data _temp_macro_calls;
            set _temp_lines;
            length macro_name $32 _i 8;
            
            /* Find all % patterns */
            _i = 1;
            do while(_i <= length(line));
                if substr(line, _i, 1) = '%' and
                   prxmatch('/[A-Za-z_]/', substr(line, _i+1, 1)) > 0 then do;
                    /* Extract word after % - only fires when % is followed by letter/underscore */
                    _word = scan(substr(line, _i+1), 1, ' (;,)');
                    if _word ne '' then do;
                        /* Exclude common SAS keywords and macro statements */
                        if upcase(_word) not in (
                                          /* Macro language statements */
                                          'MACRO', 'MEND', 'LET', 'IF', 'THEN',
                                          'ELSE', 'DO', 'END', 'TO', 'BY', 'UNTIL',
                                          'WHILE', 'GOTO', 'RETURN', 'GLOBAL', 'LOCAL',
                                          'PUT', 'INCLUDE', 'ABORT',
                                          /* Macro quoting/string functions */
                                          'STR', 'NRSTR', 'QUOTE', 'NRQUOTE',
                                          'BQUOTE', 'NRBQUOTE', 'UNQUOTE', 'SUPERQ',
                                          /* Macro evaluation functions */
                                          'EVAL', 'SYSEVALF', 'SYSFUNC', 'SYSCALL',
                                          /* Common SAS functions used via %sysfunc */
                                          'SUBSTR', 'SCAN', 'UPCASE', 'LOWCASE',
                                          'INDEX', 'LENGTH', 'TRIM', 'LEFT', 'RIGHT',
                                          'COMPRESS', 'STRIP', 'TRANWRD', 'TRANSLATE',
                                          'CAT', 'CATS', 'CATT', 'CATX',
                                          'OPEN', 'CLOSE', 'EXIST', 'VARNUM',
                                          'QTRIM', 'NLITERAL', 'KSTRIP', 'KCMPRES'
                                         ) then do;
                            macro_name = _word;
                            output;
                        end;
                    end;
                    _i = _i + length(_word) + 1;
                end;
                else _i = _i + 1;
            end;
            keep program folder_path macro_name line_num;
        run;

        proc append base=macro_calls data=_temp_macro_calls force; run;

        /* Extract dataset references (lib.dataset) */
        data _temp_datasets;
            set _temp_lines;
            length library $32 dataset $32 ref_type $10 _word $100;
            
            /* Look for keywords followed by lib.dataset */
            if index(line_upper, 'DATA ') > 0 or 
               index(line_upper, 'SET ') > 0 or
               index(line_upper, 'MERGE ') > 0 or
               index(line_upper, 'UPDATE ') > 0 or
               index(line_upper, 'FROM ') > 0 then do;
               
                /* Check each word for lib.dataset pattern */
                _i = 1;
                do while(scan(line, _i, ' ;()') ne '');
                    _word = scan(line, _i, ' ;()');
                    if index(_word, '.') > 0 and index(_word, '.') < length(_word) then do;
                        library = scan(_word, 1, '.');
                        dataset = scan(_word, 2, '.');
                        
                        /* Determine reference type */
                        if index(line_upper, 'DATA ') > 0 then ref_type = 'DATA';
                        else if index(line_upper, 'SET ') > 0 then ref_type = 'SET';
                        else if index(line_upper, 'MERGE ') > 0 then ref_type = 'MERGE';
                        else if index(line_upper, 'UPDATE ') > 0 then ref_type = 'UPDATE';
                        else if index(line_upper, 'FROM ') > 0 then ref_type = 'FROM';
                        
                        /* Validate both library and dataset are legal SAS names */
                        if library ne '' and dataset ne '' and
                           prxmatch('/^[A-Za-z_][A-Za-z0-9_]*$/', strip(library)) > 0 and
                           prxmatch('/^[A-Za-z_][A-Za-z0-9_]*$/', strip(dataset)) > 0 then output;
                    end;
                    _i = _i + 1;
                end;
            end;
            keep program folder_path library dataset ref_type line_num;
        run;

        proc append base=dataset_refs data=_temp_datasets force; run;

        /* Extract %INCLUDE statements */
        data _temp_includes;
            set _temp_lines;
            length include_path $500;
            
            if index(line_upper, '%INCLUDE') > 0 then do;
                _pos = index(line_upper, '%INCLUDE');
                include_path = substr(line, _pos + 8);
                include_path = compress(include_path, '"' || "'" || ';');
                include_path = strip(include_path);
                
                if include_path ne '' then output;
            end;
            keep program folder_path include_path;
        run;

        proc append base=includes data=_temp_includes force; run;

        /* Extract PROC usage */
        data _temp_procs;
            set _temp_lines;
            length proc_name $32;
            
            if index(line_upper, 'PROC ') > 0 then do;
                _pos = index(line_upper, 'PROC ');
                _rest = substr(line_upper, _pos + 5);
                proc_name = scan(_rest, 1, ' ;');
                if proc_name ne '' then output;
            end;
            keep program folder_path proc_name line_num;
        run;

        proc append base=proc_usage data=_temp_procs force; run;

        /* Extract banner metadata */
        data _temp_banner;
            length program $200 folder_path $500 path $500
                   title $500 description $2000 owner $200
                   created_date $30 last_modified_date $30
                   app_category $30
                   bls_cost_center $100 business_process $200
                   location $200 data_col $200 gitlab $200
                   cost_center_title $100 office_code $50
                   office_title $100 item_type $50
                   _line $32767 _line_upper $32767
                   _val $500 _rest $500 _date $30
                   _inner $500 _desc_buffer $2000
                   _is_sp 8 _pos 8 _in_desc 8;
            retain owner '' created_date '' last_modified_date ''
                   _in_desc 0 _desc_buffer '' _is_sp 0;

            %* Detect stored procedure: _SP suffix or meta/metadata folder ;
            if _n_ = 1 then do;
                _is_sp = 0;
                if upcase(reverse(scan(reverse("&program_name"), 1, '.'))) = 'SAS' then do;
                    if upcase(scan(reverse("&program_name"), 2, '_.')) = 'PS' then _is_sp = 1;
                end;
                if index(upcase("&folder_path"), '\META') > 0 then _is_sp = 1;
            end;

            %* If stored procedure skip reading lines entirely ;
            if _is_sp = 1 then do;
                if eof then do;
                    program          = "&program_name";
                    folder_path      = "&folder_path";
                    path             = "&filepath_quoted";
                    title            = "&program_name";
                    owner            = 'Stored Procedure';
                    created_date     = 'Stored Procedure';
                    description      = 'Stored Procedure';
                    last_modified_date = '';
                    app_category     = 'Production';
                    bls_cost_center  = ''; business_process = '';
                    location         = ''; data_col         = '';
                    gitlab           = ''; cost_center_title= '';
                    office_code      = ''; office_title     = '';
                    item_type        = '';
                    output;
                end;
                return;
            end;

            infile "&filepath_quoted" truncover end=eof lrecl=32767;
            input _line $32767.;
            _line       = compress(_line, '0D'x);
            _line_upper = upcase(strip(_line));

            %* Created date and Owner ;
            %* Handles: CREATED: | CREATED (no colon) | CREATE DATE: | CREATE: ;
            if created_date = '' and index(_line, '/*') > 0 and
               (index(_line_upper, 'CREATED:') > 0 or
                index(_line_upper, 'CREATE DATE:') > 0 or
                index(_line_upper, 'CREATE:') > 0 or
                prxmatch('/CREATED\s+\d/', _line_upper) > 0)
            then do;
                if index(_line_upper, 'CREATE DATE:') > 0 then do;
                    _pos  = index(_line_upper, 'CREATE DATE:');
                    _rest = strip(substr(_line, _pos + 12));
                end;
                else if index(_line_upper, 'CREATED:') > 0 then do;
                    _pos  = index(_line_upper, 'CREATED:');
                    _rest = strip(substr(_line, _pos + 8));
                end;
                else if index(_line_upper, 'CREATE:') > 0 then do;
                    _pos  = index(_line_upper, 'CREATE:');
                    _rest = strip(substr(_line, _pos + 7));
                end;
                else do;
                    _pos  = prxmatch('/CREATED\s+/', _line_upper);
                    %* Skip past CREATED keyword - date is the first token ;
                    _rest = strip(substr(_line, _pos + 7));
                end;
                if index(_rest, '*/') > 0 then
                    _rest = strip(substr(_rest, 1, index(_rest, '*/') - 1));
                _rest = strip(_rest);

                %* Find any date pattern anywhere in _rest ;
                %* Covers: MM/DD/YYYY, MM/YYYY, word-month dates (Nov 08 2010 / April 05, 2010) ;
                _rx_date = prxparse('/(?:'
                    || '\d{1,2}\/\d+\/\d{2,4}'
                    || '|\d{1,2}\/\d{4}'
                    || '|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*'
                    ||    '\s+\d{1,2},?\s+\d{4}'
                    || ')/i');
                _pos    = prxmatch(_rx_date, _rest);
                _dlen   = 0;
                if _pos > 0 then
                    call prxsubstr(_rx_date, _rest, _pos, _dlen);

                if _pos = 0 then do;
                    %* No date found - entire value is the owner name ;
                    %* Only set owner if not already captured from a prior Author: line ;
                    if _rest ne '' and owner = '' then owner = strip(_rest);
                end;
                else if _pos = 1 then do;
                    %* Date starts the string - standard layout: date then name ;
                    created_date = strip(substr(_rest, 1, _dlen));
                    if length(strip(created_date)) < length(strip(_rest)) then
                        owner = strip(substr(_rest, _dlen + 1));
                end;
                else do;
                    %* Date is not at start - non-standard layout: name then date ;
                    created_date = strip(substr(_rest, _pos, _dlen));
                    owner = strip(substr(_rest, 1, _pos - 1));
                end;

                %* Explicit Author: keyword overrides anything above ;
                if index(upcase(_rest), 'AUTHOR:') > 0 then do;
                    _pos  = index(upcase(_rest), 'AUTHOR:');
                    owner = strip(substr(_rest, _pos + 7));
                    if index(owner, '*/') > 0 then
                        owner = strip(substr(owner, 1, index(owner, '*/') - 1));
                end;

                %* Strip parenthetical notes from owner ;
                if index(owner, '(') > 0 then
                    owner = strip(substr(owner, 1, index(owner, '(') - 1));
                %* Final cleanup: strip stray asterisks only - NOT slashes (dates contain slashes) ;
                do while (length(owner) > 0 and substr(owner, length(strip(owner)), 1) = '*');
                    owner = strip(substr(owner, 1, length(strip(owner)) - 1));
                end;
                do while (length(owner) > 0 and substr(owner, 1, 1) = '*');
                    owner = strip(substr(owner, 2));
                end;
            end;

            %* Standalone Author: line - captures owner when on its own line ;
            if owner = '' and index(_line_upper, 'AUTHOR:') > 0
               and index(_line, '/*') > 0 then do;
                _pos  = index(_line_upper, 'AUTHOR:');
                _rest = strip(substr(_line, _pos + 7));
                if index(_rest, '*/') > 0 then
                    _rest = strip(substr(_rest, 1, index(_rest, '*/') - 1));
                _rest = strip(compress(_rest, '*/'));
                if _rest ne '' then owner = _rest;
            end;

            %* Last Modified Date: keep overwriting so last occurrence wins ;
            %* Handles: MODIFIED: | UPDATED: | MODIFIED (no colon) | UPDATED (no colon) ;
            if index(_line, '/*') > 0 and
               (index(_line_upper, 'MODIFIED:') > 0 or
                index(_line_upper, 'UPDATED:') > 0 or
                prxmatch('/MODIFIED\s+\d/', _line_upper) > 0 or
                prxmatch('/UPDATED\s+\d/', _line_upper) > 0)
            then do;
                if index(_line_upper, 'MODIFIED:') > 0 then
                    _pos = index(_line_upper, 'MODIFIED:') + 9;
                else if index(_line_upper, 'UPDATED:') > 0 then
                    _pos = index(_line_upper, 'UPDATED:') + 8;
                else if prxmatch('/MODIFIED\s+/', _line_upper) > 0 then
                    _pos = prxmatch('/MODIFIED\s+/', _line_upper) + 8;
                else
                    _pos = prxmatch('/UPDATED\s+/', _line_upper) + 7;
                _rest = strip(substr(_line, _pos));
                if index(_rest, '*/') > 0 then
                    _rest = strip(substr(_rest, 1, index(_rest, '*/') - 1));
                _date = scan(strip(_rest), 1, ' ');
                %* Only store if date token starts with a digit (avoids Replaced, */, etc.) ;
                if _date ne '' and prxmatch('/^\d/', _date) > 0 then
                    last_modified_date = _date;
            end;

            %* Description trigger: PURPOSE/DESCRIPTION: or PURPOSE: must be the ;
            %* first non-space token after stripping comment opener and any leading stars ;
            if _in_desc = 0 and index(_line, '/*') > 0 then do;
                %* Extract everything after the comment opener (handles /** too) ;
                _val = strip(substr(_line, index(_line, '/*') + 2));
                %* Strip any leading asterisks left over from /** style openers ;
                do while(length(_val) > 0 and substr(_val, 1, 1) = '*');
                    _val = strip(substr(_val, 2));
                end;
                %* First word must BE the keyword - include slash as delimiter ;
                %* so PURPOSE/DESCRIPTION: splits to 'PURPOSE' as first token ;
                if upcase(scan(_val, 1, ' :/')) = 'PURPOSE' or
                   upcase(scan(_val, 1, ' :/')) = 'DESCRIPTION' then do;
                    _in_desc = 1;
                    %* Advance past the keyword itself ;
                    if index(upcase(_val), 'PURPOSE/DESCRIPTION:') > 0 then
                        _pos = index(upcase(_val), 'PURPOSE/DESCRIPTION:') + 20;
                    else if index(upcase(_val), 'PURPOSE:') > 0 then
                        _pos = index(upcase(_val), 'PURPOSE:') + 8;
                    else
                        _pos = index(upcase(_val), 'DESCRIPTION:') + 12;
                    _val = strip(substr(_val, _pos));
                    %* Strip closing comment marker ;
                    if index(_val, '*/') > 0 then
                        _val = substr(_val, 1, index(_val, '*/') - 1);
                    %* Strip leading and trailing asterisks, preserve internal spaces ;
                    _val = strip(_val);
                    do while(length(_val) > 0 and substr(_val, 1, 1) = '*');
                        _val = strip(substr(_val, 2));
                    end;
                    do while(length(_val) > 0 and
                             substr(_val, length(strip(_val)), 1) = '*');
                        _val = strip(substr(_val, 1, length(strip(_val)) - 1));
                    end;
                    %* Skip bracket labels like [Main Source Code] - not real description ;
                    if prxmatch('/^\[.*\]$/', strip(_val)) > 0 then _val = '';
                    if _val ne '' then _desc_buffer = _val;
                end;
            end;
            else if _in_desc = 1 and index(_line, '/*') > 0 then do;
                %* Blank comment line (just /* or /* */) - spacer, skip but keep collecting ;
                if compress(_line, ' /*') = '' then do;
                    %* spacer - do nothing, continue ;
                end;
                else do;
                    %* Extract content between comment markers ;
                    _val = strip(_line);
                    if index(_val, '/*') > 0 then
                        _val = substr(_val, index(_val, '/*') + 2);
                    if index(_val, '*/') > 0 then
                        _val = substr(_val, 1, index(_val, '*/') - 1);
                    _val = strip(_val);
                    %* Strip leading stars FIRST so section check sees keywords not '*' ;
                    do while(length(_val) > 0 and substr(_val, 1, 1) = '*');
                        _val = strip(substr(_val, 2));
                    end;
                    %* Stop on separator lines: all dashes, equals, stars ;
                    if compress(_val, ' -*=') = '' then _in_desc = 0;
                    %* Stop on known section header keywords ;
                    else if upcase(scan(_val, 1, ' :[]')) in
                        ('INPUT', 'OUTPUT', 'OUTPUTS', 'EXTERNAL', 'MACRO', 'MACROS',
                         'INTERMEDIATE', 'VARIABLES', 'PARAMTERS', 'PARAMETERS',
                         'FILES', 'REPORTS', 'TABLES', 'DATASETS', 'CREATED',
                         'MODIFIED', 'UPDATED', 'AUTHOR', 'REASON', 'NOTES',
                         'HISTORY') then _in_desc = 0;
                    else do;
                        %* Strip leading and trailing asterisks, preserve internal spaces ;
                        do while(length(_val) > 0 and substr(_val, 1, 1) = '*');
                            _val = strip(substr(_val, 2));
                        end;
                        do while(length(_val) > 0 and
                                 substr(_val, length(strip(_val)), 1) = '*');
                            _val = strip(substr(_val, 1, length(strip(_val)) - 1));
                        end;
                        %* Skip bracket labels like [Main Source Code] ;
                        if prxmatch('/^\[.*\]$/', strip(_val)) > 0 then _val = '';
                        if _val ne '' then do;
                            if _desc_buffer = '' then _desc_buffer = _val;
                            else _desc_buffer = strip(_desc_buffer) || ' ' || _val;
                        end;
                    end;
                end;
            end;
            %* Application Category ;
            if index(upcase(folder_path), '\UTIL') > 0 then
                app_category = 'Utility Program';
            else
                app_category = 'Production';

            %* Output one row per file at end of file ;
            if eof then do;
                path        = "&filepath_quoted";
                program     = "&program_name";
                folder_path = "&folder_path";
                %* Title is simply the program filename ;
                title       = "&program_name";
                description = strip(_desc_buffer);
                bls_cost_center   = ''; business_process = '';
                location          = ''; data_col         = '';
                gitlab            = ''; cost_center_title= '';
                office_code       = ''; office_title     = '';
                item_type         = '';
                output;
            end;

            keep program folder_path path title description owner
                 created_date last_modified_date app_category
                 bls_cost_center business_process location data_col
                 gitlab cost_center_title office_code office_title item_type;
        run;

        proc append base=sas_inventory data=_temp_banner force; run;


        /* Clean up temporary datasets */
        proc datasets library=work nolist;
            delete _temp_: ;
        quit;
    
    %end;
    %else %do;
        %put WARNING: ========================================;
        %put WARNING: File not found: &filepath_quoted;
        %put WARNING: ========================================;
    %end;

%mend parse_sas_file;

/* Example usage for Windows:

%export_sas_references(
    input_dir=C:/Users/YourName/Template,
    output_file=C:/Users/YourName/Desktop/sas_references.xlsx
);

Note: The macro automatically searches through ALL subfolders recursively.
      The output will show which subfolder each program came from.

*/


%export_sas_references(
    input_dir=C:\Users\Wiley_J\OneDrive - US Department of Labor - BLS\Desktop\test_case\template_eci,
    output_file=C:\Users\Wiley_J\OneDrive - US Department of Labor - BLS\Desktop\test_case\inventory_output_eci.xlsx);