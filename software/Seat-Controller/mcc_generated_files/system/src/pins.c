/**
 * Generated Driver File
 * 
 * @file pins.c
 * 
 * @ingroup  pinsdriver
 * 
 * @brief This is generated driver implementation for pins. 
 *        This file provides implementations for pin APIs for all pins selected in the GUI.
 *
 * @version Driver Version 3.1.1
*/

/*
© [2026] Microchip Technology Inc. and its subsidiaries.

    Subject to your compliance with these terms, you may use Microchip 
    software and any derivatives exclusively with Microchip products. 
    You are responsible for complying with 3rd party license terms  
    applicable to your use of 3rd party software (including open source  
    software) that may accompany Microchip software. SOFTWARE IS ?AS IS.? 
    NO WARRANTIES, WHETHER EXPRESS, IMPLIED OR STATUTORY, APPLY TO THIS 
    SOFTWARE, INCLUDING ANY IMPLIED WARRANTIES OF NON-INFRINGEMENT,  
    MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE. IN NO EVENT 
    WILL MICROCHIP BE LIABLE FOR ANY INDIRECT, SPECIAL, PUNITIVE, 
    INCIDENTAL OR CONSEQUENTIAL LOSS, DAMAGE, COST OR EXPENSE OF ANY 
    KIND WHATSOEVER RELATED TO THE SOFTWARE, HOWEVER CAUSED, EVEN IF 
    MICROCHIP HAS BEEN ADVISED OF THE POSSIBILITY OR THE DAMAGES ARE 
    FORESEEABLE. TO THE FULLEST EXTENT ALLOWED BY LAW, MICROCHIP?S 
    TOTAL LIABILITY ON ALL CLAIMS RELATED TO THE SOFTWARE WILL NOT 
    EXCEED AMOUNT OF FEES, IF ANY, YOU PAID DIRECTLY TO MICROCHIP FOR 
    THIS SOFTWARE.
*/

#include "../pins.h"

void (*IO_RA0_InterruptHandler)(void);
void (*IO_RA1_InterruptHandler)(void);
void (*IO_RA2_InterruptHandler)(void);

void PIN_MANAGER_Initialize(void)
{
   /**
    LATx registers
    */
    LATA = 0x0;
    LATB = 0x0;
    LATC = 0x0;
    /**
    ODx registers
    */
    ODCONA = 0x0;
    ODCONB = 0x0;
    ODCONC = 0x0;

    /**
    TRISx registers
    */
    TRISA = 0xFF;
    TRISB = 0xFE;
    TRISC = 0xF1;
    TRISE = 0x8;

    /**
    ANSELx registers
    */
    ANSELA = 0xF8;
    ANSELB = 0xFC;
    ANSELC = 0xFF;

    /**
    WPUx registers
    */
    WPUA = 0x0;
    WPUB = 0x0;
    WPUC = 0x0;
    WPUE = 0x0;


    /**
    SLRCONx registers
    */
    SLRCONA = 0xFF;
    SLRCONB = 0xFF;
    SLRCONC = 0xFF;

    /**
    INLVLx registers
    */
    INLVLA = 0xFF;
    INLVLB = 0xFF;
    INLVLC = 0xFF;
    INLVLE = 0x8;

   /**
    RxyI2C | RxyFEAT registers   
    */
    RB1I2C = 0x0;
    RB2I2C = 0x0;
    RC3I2C = 0x0;
    RC4I2C = 0x0;
    /**
    PPS registers
    */
    CANRXPPS = 0x9; //RB1->CAN1:CANRX;
    RB0PPS = 0x46;  //RB0->CAN1:CANTX;
    RC3PPS = 0x1C;  //RC3->PWM3_16BIT:PWM31;
    RC2PPS = 0x1A;  //RC2->PWM2_16BIT:PWM21;
    RC1PPS = 0x18;  //RC1->PWM1_16BIT:PWM11;

   /**
    IOCx registers 
    */
    IOCAP = 0x7;
    IOCAN = 0x4;
    IOCAF = 0x0;
    IOCBP = 0x0;
    IOCBN = 0x0;
    IOCBF = 0x0;
    IOCCP = 0x0;
    IOCCN = 0x0;
    IOCCF = 0x0;
    IOCEP = 0x0;
    IOCEN = 0x0;
    IOCEF = 0x0;

    IO_RA0_SetInterruptHandler(IO_RA0_DefaultInterruptHandler);
    IO_RA1_SetInterruptHandler(IO_RA1_DefaultInterruptHandler);
    IO_RA2_SetInterruptHandler(IO_RA2_DefaultInterruptHandler);

    // Enable PIE0bits.IOCIE interrupt 
    PIE0bits.IOCIE = 1; 
}
  
void PIN_MANAGER_IOC(void)
{
    // interrupt on change for pin IO_RA0
    if(IOCAFbits.IOCAF0 == 1)
    {
        IO_RA0_ISR();  
    }
    // interrupt on change for pin IO_RA1
    if(IOCAFbits.IOCAF1 == 1)
    {
        IO_RA1_ISR();  
    }
    // interrupt on change for pin IO_RA2
    if(IOCAFbits.IOCAF2 == 1)
    {
        IO_RA2_ISR();  
    }
}
   
/**
   IO_RA0 Interrupt Service Routine
*/
void IO_RA0_ISR(void) {

    // Add custom IO_RA0 code

    // Call the interrupt handler for the callback registered at runtime
    if(IO_RA0_InterruptHandler)
    {
        IO_RA0_InterruptHandler();
    }
    IOCAFbits.IOCAF0 = 0;
}

/**
  Allows selecting an interrupt handler for IO_RA0 at application runtime
*/
void IO_RA0_SetInterruptHandler(void (* InterruptHandler)(void)){
    IO_RA0_InterruptHandler = InterruptHandler;
}

/**
  Default interrupt handler for IO_RA0
*/
void IO_RA0_DefaultInterruptHandler(void){
    // add your IO_RA0 interrupt custom code
    // or set custom function using IO_RA0_SetInterruptHandler()
}
   
/**
   IO_RA1 Interrupt Service Routine
*/
void IO_RA1_ISR(void) {

    // Add custom IO_RA1 code

    // Call the interrupt handler for the callback registered at runtime
    if(IO_RA1_InterruptHandler)
    {
        IO_RA1_InterruptHandler();
    }
    IOCAFbits.IOCAF1 = 0;
}

/**
  Allows selecting an interrupt handler for IO_RA1 at application runtime
*/
void IO_RA1_SetInterruptHandler(void (* InterruptHandler)(void)){
    IO_RA1_InterruptHandler = InterruptHandler;
}

/**
  Default interrupt handler for IO_RA1
*/
void IO_RA1_DefaultInterruptHandler(void){
    // add your IO_RA1 interrupt custom code
    // or set custom function using IO_RA1_SetInterruptHandler()
}
   
/**
   IO_RA2 Interrupt Service Routine
*/
void IO_RA2_ISR(void) {

    // Add custom IO_RA2 code

    // Call the interrupt handler for the callback registered at runtime
    if(IO_RA2_InterruptHandler)
    {
        IO_RA2_InterruptHandler();
    }
    IOCAFbits.IOCAF2 = 0;
}

/**
  Allows selecting an interrupt handler for IO_RA2 at application runtime
*/
void IO_RA2_SetInterruptHandler(void (* InterruptHandler)(void)){
    IO_RA2_InterruptHandler = InterruptHandler;
}

/**
  Default interrupt handler for IO_RA2
*/
void IO_RA2_DefaultInterruptHandler(void){
    // add your IO_RA2 interrupt custom code
    // or set custom function using IO_RA2_SetInterruptHandler()
}
/**
 End of File
*/