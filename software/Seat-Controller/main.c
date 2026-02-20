 /*
 * MAIN Generated Driver File
 * 
 * @file main.c
 * 
 * @defgroup main MAIN
 * 
 * @brief This is the generated driver implementation file for the MAIN driver.
 *
 * @version MAIN Driver Version 1.0.2
 *
 * @version Package Version: 3.1.2
*/

/*
� [2026] Microchip Technology Inc. and its subsidiaries.

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
#include "mcc_generated_files/system/system.h"

/*
    Main application
*/


struct CAN_MSG_OBJ RX_message1, RX_message2;// structure for received message
bool vote, vote_request, voted, occupancy, FIFO1_received, FIFO2_received;

void LEDhandler(uint16_t R, uint16_t G, uint16_t B)
{
    PWM1_16BIT_SetSlice1Output1DutyCycleRegister(R);
    PWM1_16BIT_SetSlice1Output2DutyCycleRegister(R);
    
    
    PWM2_16BIT_SetSlice1Output1DutyCycleRegister(G);
    PWM2_16BIT_SetSlice1Output2DutyCycleRegister(G);
    
    
    PWM3_16BIT_SetSlice1Output1DutyCycleRegister(B);
    PWM3_16BIT_SetSlice1Output2DutyCycleRegister(B);
}

// a large portion of this was taken from https://github.com/microchip-pic-avr-examples/pic18f47q83-can-2-basic-operation-mplab-mcc
void TX_message_sender(bool data0,bool data1,bool data2,bool data3,
        bool data4,bool data5,bool data6,bool data7)
{
    uint8_t TX_data = (uint8_t)((data0 << 0)|(data1 << 1)|(data2 << 2)|(data3 << 3)|
    (data4 << 4)|(data5 << 5)|(data6 << 6)|(data7 << 7));

    
    struct CAN_MSG_OBJ Transmission; //create transmission message
    Transmission.field.brs=CAN_NON_BRS_MODE; // No bit rate switching
    Transmission.field.dlc=DLC_8; //8 data bytes
    Transmission.field.formatType=CAN_2_0_FORMAT; //CAN 2.0 frames 
    Transmission.field.frameType=CAN_FRAME_DATA; //Data frame
    Transmission.field.idType=CAN_FRAME_STD; //Standard ID
    Transmission.msgId=0x100; //ID of 0x100
    Transmission.data=&TX_data; //transmit the data from the data bytes
    if(CAN_TX_FIFO_AVAILABLE == (CAN1_TransmitFIFOStatusGet(CAN1_TXQ) & CAN_TX_FIFO_AVAILABLE))//ensure that the TXQ has space for a message
    {
        CAN1_Transmit(CAN1_TXQ, &Transmission); //transmit frame
    }  
}

void RX_important_message_handler(struct CAN_MSG_OBJ *message)
{
    
}

void RX_message_handler(struct CAN_MSG_OBJ *message) //handler for less important received messages
{    
    LEDhandler(message->data[1],message->data[2],message->data[3]); 
    if (message->data[0] & (1 << 0)) //vote requested
    {
        vote_request = 1;
    }
    else
    {
        vote_request = 0;
    }
    if (message->data[0] & (1 << 1)) //vote ends
    {
        TX_message_sender(voted,vote,occupancy,0, 0,0,0,0);
        voted = 0;
        vote_request = 0;
    }
    else
    {
        TX_message_sender(0,0,occupancy,0, 0,0,0,0);
    }
}


//interrupt handlers

//PWM INTERRUPTS
void PWM1_INT_handler(void)
{
    PWM1_16BIT_LoadBufferRegisters();
}

void PWM2_INT_handler(void)
{
    PWM2_16BIT_LoadBufferRegisters();
}

void PWM3_INT_handler(void)
{
    PWM3_16BIT_LoadBufferRegisters();
}

//PIN INTERRUPTS
void RA0_INT_handler(void) //voted no
{
    if (vote_request)
    {
        vote = 0;
        voted = 1;
    }  
    else
    {
        voted = 0;
    }
}

void RA1_INT_handler(void) //voted yes
{
    if (vote_request)
    {
        vote = 1;
        voted = 1;
    }  
    else
    {
        voted = 0;
    }
}

void RA2_INT_handler(void) //occupancy sensor
{
    if (IO_RA2_GetValue())
    {
        occupancy = 1;
    }
    else
    {
        occupancy = 0;
    }
}

//CAN INTERRUPTS
void CANRX_FIFO1_ISR(void) //handler for receiving messages on FIFO1
{
    CAN1_ReceiveMessageGet(CAN1_FIFO_1, &RX_message1);
    FIFO1_received = 1;
}

void CANRX_FIFO2_ISR(void) //handler for receiving messages on FIFO2
{
    CAN1_ReceiveMessageGet(CAN1_FIFO_2, &RX_message2);
    FIFO2_received = 1;
}

//MAIN PROGRAM

int main(void)
{   
    SYSTEM_Initialize();
    PWM1_16BIT_Enable();
    PWM2_16BIT_Enable();
    PWM3_16BIT_Enable();
    INTERRUPT_GlobalInterruptEnable();
    Timer0_TMRInterruptEnable();
    PWM1_16BIT_Period_SetInterruptHandler(*PWM1_INT_handler);
    PWM2_16BIT_Period_SetInterruptHandler(*PWM2_INT_handler);
    PWM3_16BIT_Period_SetInterruptHandler(*PWM3_INT_handler);
    RA0_SetInterruptHandler(*RA0_INT_handler);
    RA1_SetInterruptHandler(*RA1_INT_handler);
    RA2_SetInterruptHandler(*RA2_INT_handler);
    CAN1_FIFO1NotEmptyCallbackRegister(CANRX_FIFO1_ISR);
    CAN1_FIFO2NotEmptyCallbackRegister(CANRX_FIFO2_ISR);
    Timer0_Start;
    
    while(1)
    {
        if (FIFO1_received)
        {
            RX_important_message_handler(&RX_message1);
            FIFO1_received = 0;
        }
        if (FIFO2_received)
        {
            RX_message_handler(&RX_message2);
            FIFO2_received = 0;
        }
    }
}