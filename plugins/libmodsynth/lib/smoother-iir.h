/* 
 * File:   smoother-iir.h
 * Author: Jeff Hubbard
 * 
 * This file provides the t_smoother_iir type, which can be used to smooth GUI controls values.
 * 
 * Smoother linear provides better fine-tuning of the smoothing, and only uses slightly more CPU power.
 *
 * Created on February 6, 2012, 7:12 PM
 */

#ifndef SMOOTHER_IIR_H
#define	SMOOTHER_IIR_H

#ifdef	__cplusplus
extern "C" {
#endif

#include "../lib/denormal.h"
    
typedef struct s_smoother_iir
{
    float output;
}t_smoother_iir;

inline void v_smr_iir_run(t_smoother_iir*, float);
inline void v_smr_iir_run_fast(t_smoother_iir*, float);

/* inline void v_smr_iir_run(
 * t_smoother_iir * 
 * a_smoother, float a_in)  //The input to be smoothed
 * 
 * Use t_smoother_iir->output as your new control value after running this
 */
inline void v_smr_iir_run(t_smoother_iir * a_smoother, float a_in) 
{ 
    a_smoother->output = (a_in * .01f) + ((a_smoother->output) * .99f);     
}

/* inline void v_smr_iir_run_fast(
 * t_smoother_iir * 
 * a_smoother, float a_in)  //The input to be smoothed
 * 
 * Use t_smoother_iir->output as your new control value after running this
 */
inline void v_smr_iir_run_fast(t_smoother_iir * a_smoother, float a_in) 
{ 
    a_smoother->output = f_remove_denormal((a_in * .2f) + ((a_smoother->output) * .8f));
}

t_smoother_iir * g_smr_iir_get_smoother();

t_smoother_iir * g_smr_iir_get_smoother()
{
    t_smoother_iir * f_result;
    
    if(posix_memalign((void**)&f_result, 16, sizeof(t_smoother_iir)) != 0)
    {
        return 0;
    }
    
    f_result->output = 0.0f;
    return f_result;
}

#ifdef	__cplusplus
}
#endif

#endif	/* SMOOTHER_IIR_H */

