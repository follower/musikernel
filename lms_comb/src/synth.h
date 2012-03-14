/* 
 * File:   synth.h
 * Author: Jeff Hubbard
 *
 * Created on February 26, 2012, 8:48 PM
 */

#ifndef SYNTH_H
#define	SYNTH_H

#ifdef	__cplusplus
extern "C" {
#endif

#include "ladspa.h"
#include "libmodsynth.h"
    
/*Comment these out when compiling a stable, production-ready plugin.  
 The debugging code wastes a lot of CPU, and end users don't really need to see it*/
//#define LMS_DEBUG_NOTE
//#define LMS_DEBUG_MAIN_LOOP
//#define LMS_DEBUG_MODE_QT
//#define LMS_DEBUGGER_PROJECT

/*Then you can print debug information like this:
#ifdef LMS_DEBUG_NOTE
printf("debug information");
#endif
*/
   
#define LMS_INPUT0  0
#define LMS_INPUT1  1    
#define LMS_OUTPUT0  2
#define LMS_OUTPUT1  3
/*GUI Step 11:  Add ports to the main synthesizer file that the GUI can talk to */
    
/*LMS_FIRST_CONTROL_PORT is the first port used for controls such as knobs.  All control ports must be numbered continuously,
 as they are iterated through*/
#define LMS_FIRST_CONTROL_PORT 4
#define LMS_CUTOFF  4
#define LMS_AMT  5
/*This is the last control port*/
#define LMS_LAST_CONTROL_PORT 5
#define LMS_COUNT 6 /* must be 1 + highest value above CHANGE THIS IF YOU ADD OR TAKE AWAY ANYTHING*/


#define POLYPHONY   8  //maximum voices played at one time
#define MIDI_NOTES  128  //Maximum MIDI note.  You probably don't want to change this
#define STEP_SIZE   16
    

/*GUI Step 12:  Add a variable for each control in the synth_vals type*/
typedef struct {    
    /*The variables below this line correspond to GUI controls*/
    
    LADSPA_Data cutoff;
    LADSPA_Data amt;    
    
    /*The variables below this line do NOT correspond to GUI controls*/
#ifdef LMS_DEBUG_MAIN_LOOP
    int debug_counter;
#endif
} synth_vals;

#ifdef LMS_DEBUG_MAIN_LOOP

void dump_debug_synth_vals(synth_vals*);

/*Any changes to voice_data require this to be changed*/
void dump_debug_synth_vals(synth_vals * a_data)
{
    printf("\n\nRunning dump_debug_synth_vals\n");
    printf("osc1type == %f\n", a_data->osc1type);   
    printf("res == %f\n", a_data->res);    
    printf("timbre == %f\n", a_data->cutoff);  
}

#endif

/*GUI Step 13:  Add a variable for each control in the LMS type*/
typedef struct {
    LADSPA_Data *input0;
    LADSPA_Data *input1;
    LADSPA_Data *output0;
    LADSPA_Data *output1;
    LADSPA_Data *cutoff;
    LADSPA_Data *amt;
    
    float fs;    
    t_mono_modules * mono_modules;
    synth_vals vals;
    
    int pos;
    int count;
    int buffer_pos;
    int i_mono_out;
    int i_buffer_clear;    
    
} LMS;




#ifdef	__cplusplus
}
#endif

#endif	/* SYNTH_H */

