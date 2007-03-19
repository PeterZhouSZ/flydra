#define LARGE_BUFFER

//_____  I N C L U D E S ___________________________________________________

#include "config.h"
#include "conf_usb.h"
#include "hid_task.h"
#include "stk_525.h"
#include "usb_drv.h"
#include "usb_descriptors.h"
#include "usb_standard_request.h"
#include "usb_specific_request.h"
#include "adc_drv.h"
//#include "framecount_task.h"


//_____ M A C R O S ________________________________________________________


//_____ D E F I N I T I O N S ______________________________________________



//_____ D E C L A R A T I O N S ____________________________________________

extern bit   usb_connected;
bit   new_data=FALSE;
extern  uint8_t   usb_configuration_nb;
volatile uint8_t cpt_sof=0;

volatile uint8_t trig_once_mode=0;

//! Declare function pointer to USB bootloader entry point
void (*start_bootloader) (void)=(void (*)(void))0xf000;

void set_OCR3A(uint16_t val) {
  // See "Accessing 16-bit Registers" of the AT90USB1287 datasheet

  uint8_t sreg;

  sreg = SREG; // save arithmetic state
  cli(); // disable interrupts
  OCR3A = val;
  SREG = sreg; // restore arithmetic state 

  // presumably interrupts are enabled upon function return
}

void set_OCR3B(uint16_t val) {
  // See "Accessing 16-bit Registers" of the AT90USB1287 datasheet

  uint8_t sreg;

  sreg = SREG; // save arithmetic state
  cli(); // disable interrupts
  OCR3B = val;
  SREG = sreg; // restore arithmetic state 

  // presumably interrupts are enabled upon function return
}

void set_OCR3C(uint16_t val) {
  // See "Accessing 16-bit Registers" of the AT90USB1287 datasheet

  uint8_t sreg;

  sreg = SREG; // save arithmetic state
  cli(); // disable interrupts
  OCR3C = val;
  SREG = sreg; // restore arithmetic state 

  // presumably interrupts are enabled upon function return
}

void set_ICR3(uint16_t val) {
  // See "Accessing 16-bit Registers" of the AT90USB1287 datasheet
  // icr1 is TOP for timer1

  uint8_t sreg;

  sreg = SREG; // save arithmetic state
  cli(); // disable interrupts
  ICR3 = val;
  SREG = sreg; // restore arithmetic state 

  // presumably interrupts are enabled upon function return
}

void set_TCNT3(uint16_t val) {
  // See "Accessing 16-bit Registers" of the AT90USB1287 datasheet
  uint8_t sreg;

  sreg = SREG; // save arithmetic state
  cli(); // disable interrupts
  TCNT3 = val;
  SREG = sreg; // restore arithmetic state 

  // presumably interrupts are enabled upon function return
}

uint16_t get_TCNT3(void) {
  // See "Accessing 16-bit Registers" of the AT90USB1287 datasheet

  uint16_t val;
  uint8_t sreg;
  
  sreg = SREG; // save arithmetic state
  cli(); // disable interrupts
  val = TCNT3;
  SREG = sreg; // restore arithmetic state 

  return val;
}

uint16_t get_ICR3(void) {
  // See "Accessing 16-bit Registers" of the AT90USB1287 datasheet
  // icr1 is TOP for timer1

  uint16_t val;
  uint8_t sreg;
  
  sreg = SREG; // save arithmetic state
  cli(); // disable interrupts
  val = ICR3;
  SREG = sreg; // restore arithmetic state 

  return val;
}

uint16_t get_OCR3A(void) {
  // See "Accessing 16-bit Registers" of the AT90USB1287 datasheet

  uint16_t val;
  uint8_t sreg;
  
  sreg = SREG; // save arithmetic state
  cli(); // disable interrupts
  val = OCR3A;
  SREG = sreg; // restore arithmetic state 

  return val;
}

uint16_t get_OCR3B(void) {
  // See "Accessing 16-bit Registers" of the AT90USB1287 datasheet

  uint16_t val;
  uint8_t sreg;
  
  sreg = SREG; // save arithmetic state
  cli(); // disable interrupts
  val = OCR3B;
  SREG = sreg; // restore arithmetic state 

  return val;
}

uint16_t get_OCR3C(void) {
  // See "Accessing 16-bit Registers" of the AT90USB1287 datasheet

  uint16_t val;
  uint8_t sreg;
  
  sreg = SREG; // save arithmetic state
  cli(); // disable interrupts
  val = OCR3C;
  SREG = sreg; // restore arithmetic state 

  return val;
}

void init_pwm_output(void) {
  /*
    
  n = 3 (timer3)

  Set frequency of PWM using ICRn to set TOP. (Not double-buffered,
  also, clear TCNT before setting.)  
  
  Set compare value using OCRnA.
  
  WGMn3:0 = 14
  
  */

  // set output direction on pin
  PORTC &= 0x8F; // pin C4-6 set low to start
  DDRC |= 0x70; // enable output for Output compare and PWM A-C of Timer/Counter 3

  // Set output compare to mid-point
  set_OCR3A( 10 );

  set_OCR3B( 0x0 );
  set_OCR3C( 0x0 );

  // Set TOP to 500 (if F_CLOCK = 1MHZ, this is 200 Hz)
  //set_ICR3( 5000 );
  set_ICR3( 77 );

  // ---- set TCCR1A ----------
  // set Compare Output Mode for Fast PWM
  // COM3A1:0 = 1,0 clear OC3A on compare match
  // COM3B1:0 = 1,0 clear OC3B on compare match
  // COM3C1:0 = 1,0 clear OC3B on compare match
  // WGM31, WGM30 = 1,0
  TCCR3A = 0xAA;

  // ---- set TCCR1B ----------
  // high bits = 0,0,0
  //WGM33, WGM32 = 1,1
  // CS1 = 0,0,1 (starts timer1) (clock select)
  // CS1 = 0,1,1 (starts timer1 CS=8) (clock select)
  TCCR3B = 0x1B;

  // really only care about timer3_compa_vect
  TIMSK3 = 0x07; //OCIE1A|OCIE1B|TOIE1; // XXX not sure about interrupt names // enable interrucpts
}

ISR(TIMER3_COMPA_vect) {
  if (trig_once_mode) {

    TCCR3B = (TCCR3B & 0xF8) | (0 & 0x07); // low 3 bits sets CS to 0 (stop)

    trig_once_mode=0;
  }
  //  increment_framecount_A();
}
ISR(TIMER3_COMPB_vect) {
}
ISR(TIMER3_OVF_vect) {
  // timer3 overflowed
}

//!
//! @brief This function initializes the target board ressources.
//!
//! @warning Code:?? bytes (function code length)
//!
//! @param none
//!
//! @return none
//!
//!/
void trigger_task_init(void)
{
   init_adc();
   Leds_init();
   Joy_init();
   
   init_pwm_output(); // trigger output
}





void trigger_task(void)
{
   uint8_t flags=0;
#define TASK_FLAGS_ENTER_DFU 0x01
#define TASK_FLAGS_NEW_TIMER3_DATA 0x02
#define TASK_FLAGS_DO_TRIG_ONCE 0x04
#define TASK_FLAGS_DOUT_HIGH 0x08

   uint8_t clock_select_timer3=0;
   uint32_t volatile tmp;

   uint16_t new_ocr3a;
   uint16_t new_ocr3b;
   uint16_t new_ocr3c;
   uint16_t new_icr3; // icr3 is TOP for timer3

   int64_t * framecount_ptr;

   if(usb_connected)                    
    {
      Usb_select_endpoint(ENDPOINT_BULK_OUT);    //! Get Data from Host
      if(Is_usb_receive_out()) {
	// first 8 bytes
	new_ocr3a =           Usb_read_byte()<<8; // high byte
	new_ocr3a +=          Usb_read_byte();    // low byte
	new_ocr3b =           Usb_read_byte()<<8; // high byte
	new_ocr3b +=          Usb_read_byte();    // low byte

#ifdef LARGE_BUFFER
	new_ocr3c =           Usb_read_byte()<<8; // high byte
	new_ocr3c +=          Usb_read_byte();    // low byte
#else
	new_ocr3c =           0;
#endif
	new_icr3  =           Usb_read_byte()<<8; // high byte  // icr3 is TOP for timer3
	new_icr3 +=           Usb_read_byte();    // low byte

	// next 8 bytes
	flags     =           Usb_read_byte();
	clock_select_timer3 = Usb_read_byte();
#ifdef LARGE_BUFFER
	Usb_read_byte();
	Usb_read_byte();

	Usb_read_byte();
	Usb_read_byte();
	Usb_read_byte();
	Usb_read_byte();
#endif
	Usb_ack_receive_out();

	if (flags & TASK_FLAGS_NEW_TIMER3_DATA) {
	  // update timer3
	  set_OCR3A(new_ocr3a);
	  set_OCR3B(new_ocr3b);
	  set_OCR3C(new_ocr3c);
	  set_ICR3(new_icr3);  // icr3 is TOP for timer3

	  TCCR3B = (TCCR3B & 0xF8) | (clock_select_timer3 & 0x07); // low 3 bits sets CS
	  new_data = TRUE;
	}

	if (flags & TASK_FLAGS_DO_TRIG_ONCE) {
	  //	  new_icr3 = get_ICR3();  // icr1 is TOP for timer1
	  //new_icr3--;
	  TCCR3B = (TCCR3B & 0xF8) | (0 & 0x07); // low 3 bits sets CS to 0 (stop)

	  set_TCNT3(0xFF00); // trigger overflow soon
	  //set_OCR3A(0xFE00);
	  set_OCR3A(0x00FF);
	  set_ICR3(0xFFFF);  // icr3 is TOP for timer3

	  trig_once_mode=1;

	  // start clock
	  TCCR3B = (TCCR3B & 0xF8) | (1 & 0x07); // low 3 bits sets CS
	  
	  /*
	  // XXX this doesn't seem to work 100% of the time... - ADS
	  PORTC |= 0x70; // pin C4-6 set high
	  TCCR3B = (TCCR3B & 0xF8) | (0 & 0x07); // low 3 bits sets CS to 0 (stop)

	  */
	  new_data = TRUE;
	}

      }
      if (flags & TASK_FLAGS_ENTER_DFU) //! Check if we received DFU mode command from host
	{
	  Usb_detach();                    // detach from USB...
	  TCCR3B = 0x00; // disable trigger outputs and timer3

	  Led0_off();
	  Led1_off();
	  Led2_off();
	  Led3_off();
	  for(tmp=0;tmp<70000;tmp++);     // pause...
	  (*start_bootloader)();
	}

      if (new_data == TRUE) {

	Usb_select_endpoint(ENDPOINT_BULK_IN);    //! Ready to send these information to the host application
	if(Is_usb_in_ready())
	  {
	    new_ocr3a = get_OCR3A();
	    new_ocr3b = get_OCR3B();
	    new_ocr3c = get_OCR3C();
	    new_icr3 = get_ICR3();  // icr1 is TOP for timer1

	    //get_framecount_A(framecount_ptr);

	    Usb_write_byte(((uint8_t*)framecount_ptr)[0]);
	    Usb_write_byte(((uint8_t*)framecount_ptr)[1]);
	    Usb_write_byte(((uint8_t*)framecount_ptr)[2]);
	    Usb_write_byte(((uint8_t*)framecount_ptr)[3]);

	    Usb_write_byte(((uint8_t*)framecount_ptr)[4]);
	    Usb_write_byte(((uint8_t*)framecount_ptr)[5]);
	    Usb_write_byte(((uint8_t*)framecount_ptr)[6]);
	    Usb_write_byte(((uint8_t*)framecount_ptr)[7]);

	    Usb_write_byte(PORTC);
	    Usb_write_byte(TCCR3B);
	    Usb_write_byte(0x77);
	    Usb_write_byte(0x77);

	    Usb_write_byte(0x77);
	    Usb_write_byte(0x77);
	    Usb_write_byte(0x77);
	    Usb_write_byte(0x77);
	    
	    Usb_ack_fifocon();               //! Send data over the USB
	    new_data = FALSE;
	  }
      }


      if (flags & TASK_FLAGS_DOUT_HIGH) {
	// force output compare A
	set_OCR3A(0xFE00U);
	//set_OCR3B(new_ocr3b);
	//set_OCR3C(new_ocr3c);
	set_ICR3(0xFEFFU);
	set_TCNT3(0xFFFFU);
	Led0_on();
	TCCR3B = (TCCR3B & 0xF8) | (1 & 0x07); // start clock
	while (1) {
	  // wait for timer to roll over and thus trigger output compare
	  uint32_t tmp_tcnt = get_TCNT3();
	  if (tmp_tcnt < 0xFFFFU) {
	    break;
	  }
	}
	Led3_on();
	TCCR3B = (TCCR3B & 0xF8) | (0 & 0x07); // stop clock
      }


    }
}

//! @brief sof_action
//!
//! This function increments the cpt_sof counter each times
//! the USB Start Of Frame interrupt subroutine is executed (1ms)
//! Usefull to manage time delays
//!
//! @warning Code:?? bytes (function code length)
//!
//! @param none
//!
//! @return none
void sof_action()
{
   cpt_sof++;
}
