/********************************************   Version 1.30   ***************/
/*-------------------------------------------------------------------------- */
/*                                                                           */
/*                                                        ORACLE Version     */
/* Program Name: C:/DCPS/programs/dc_records2.sas                            */
/* Official Name: Selection of schedules for data conversion                 */
/*-------------------------------------------------------------------------- */
/*                                                                           */
/*                                                                           */
/* Purpose:   This program selects schedules from the ices_sched             */
/*            table that are eligible to enter data                          */
/*            conversion for the National Compensation Survey (NCS).         */
/*            The selected schedules are stored in                           */
/*            the <dc_sched_control> dataset and ares used                   */
/*            throughout data conversion processing.                         */   
/*                                                                           */
/* Terminology note: The term "viable" means a schedule that did or could    */
/*                   have provided usable data.  Usable schedules and        */
/*                   refusals are both considered viable.  Out-of-scope      */
/*                   and out-of-business schedules are not considered        */
/*                   viable.  Even with a willing respondent, these are      */
/*                   schedules for companies that did not have usable        */
/*                   information for the survey.                             */
/*                                                                           */
/*                                                                           */
/* Input:     [Tables]:       Ices_sched table from the NCS2001 database     */
/*            [Files]:                                                       */
/*            [SAS Datasets]: /home/fordj/ices_sched                         */
/*                            (This program will be                          */
/*                            changed in the future so that data comes from  */
/*                            a datastore that will also be entitled         */
/*                            'ices_sched.)                                  */
/*                                                                           */
/* Output:    [Tables]:       None yet--see note on datasets                 */
/*            [Files]:        None                                           */
/*            [SAS Datasets]: dc_sched_control.                              */
/*                                                                           */
/*            [Reports]:      None                                           */
/*                                                                           */
/*Intermediate                                                               */
/* variables:                   description                       Data type  */
/*--------------   ----------------------------------------     ------------ */
/*  NONE                                                                     */
/*                                                                           */
/*                                                                           */
/* Created:   04/23/2003      Jason Ford                                     */
/*                                                                           */
/* Updated:   04/2004                                                        */
/* Reason:    To put in the information from the Statistical Methods         */
/*            Group override codes                                           */
/*                                                                           */
/* Updated:  07/2004                                                         */
/* Reason:   To use a new method of extracting data.  Data are extracted     */
/*           from Ices_sched if  the  index_sched='Y' and the                */
/*           overlap_flag='N' and the estab_init_use= 'Y' and the            */
/*           final_wage_status is either' USE','TNR', 'STR','VAC',           */
/*           or 'REF'.  Changes to the meanings of variables allowed         */
/*           for this much simpler algorithm for extracting the needed       */ 
/*           data.  The prior algorithm was much more complex and            */
/*			 had one set of rules for initiations and one set of rules       */
/*			 for updates.                                                    */ 
/*                                                                           */
/* Updated:   03/19/2009                                                     */
/* Reason:    We added Source_rotation_group_number to the variables pulled  */
/*            for Dc_sched_control.  The problem was that using the          */
/*            rotation_group_number caused problems because the overlap      */
/*            sample_member_id can change from quarter to quarter.  See the  */
/*            paper "rotation group number problem" at                       */
/*            \\Ocspapps1\dcpspostcollection\Process Documentation           */
/*                                                                           */
/* Modified:  04/24/2014		  Peter Haines                               */
/* Reason:    Add libname Orcllib for Oracle.	            		         */
/*            Use two Libnames, one for Sybase and one for Oracle.           */
/*****************************************************************************/



/*Options and referencing information--irrelevant for reviewers.*/

*options mlogic fullstimer mprint symbolgen source2 mrecall mautosource spool;
*%let mcyclepq=131;      /*Always set to the prior cycle.*/
*%let mcycle  =132;      /*always set to the current cycle.*/

*LIBNAME saslib '/home/fordj/ldt';   /*Test data stored here.*/


/*Libname ncsecidb sybase database = ncsecidev
 server=  OCSPDBSUN1
 user  =  ford_j
 password ='xxxxxx';*/


/*Libname ncsecidb sybase database = dc
 server=  OCSPDBSUN1
 user  =  ford_j
 password =  
connection=unique;*/

/*End Options and referencing information.*/


/*****************************************************************************/
/* The following proc SQL join creates the dc_sched_control table.           */
/* Data are taken from ices_sched that meet certain conditons.  The          */
/* schedules have to be part of the index (index_sched='Y'), not an          */
/* overlap (overlap_flag='N') and a schedule that is viable.  A viable       */
/* schedule is one where usable data were collected at some point (estab_    */
/* init_use='Y') and is currently viable.                                    */  
/*                                                                           */ 
/* To determine current viability, we use the final_wage_status field.  The  */
/* final wage status must be in one of the following five categories:        */
/*                                                                           */
/* 1.  Usable ('USE'):  The respondent is providing data.                    */
/* 2.  Temporary nonresponse ('TNR'): The respondent didn't provide data     */ 
/*     this cycle but is expected to do so in the future.                    */
/* 3.  Strike ('STR'): The respondent is on strike for all sampled jobs      */
/*     this cycle.                                                           */
/* 4.  Vacancy ('VAC'):  The respondent has vacancies in all sampled jobs    */
/*     this cycle.                                                           */
/* 5.  Refusal ('REF'):  The job is a permanent refusal.                     */ 
/*****************************************************************************/


proc sql;

	create table saslib.dc_sched_control as
           select  i.cycle,
		     	   i.sched format=11.,
				   i.ben_init_flag,
				   i.final_wage_status,
                   i.initiation_indicator,
                   i.eci_benefit_status,
		   		   i.rotation_group_number,
		           i.source_rotation_group_number, /*Added 3-19-2009*/
                   i.index_sched

				from
				   ORCLLIB.ices_sched as i

				where

                  i.cycle=&mCycle                            AND
                  i.index_sched=          'Y'                AND
                  i.overlap_flag=         'N'                AND
                  i.estab_init_use=       'Y'                AND
                  i.final_wage_status in  ('USE','TNR', 'STR','VAC', 'REF');
     quit;

