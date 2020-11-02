"""
selprotopy: A Protocol Binding Suite for the SEL Protocol Suite.

Supports:
  - SEL Fast Meter
  - SEL Fast Message
  - SEL Fast Operate
"""

# Import Requirements
import math
import struct


# Define Simple Function to Cast Binary Integer to List of Bools
def int_to_bool_list( number, byte_like=False, reverse=False ):
    """
    `int_to_bool_list`
    
    This function converts an integer to a list of boolean values,
    where the most significant value is stored in the highest point
    of the list. That is, a binary number: 8 would be represented as
    [False, False, False, True]
    
    Parameters
    ----------
    number:     int
                Integer to be converted to list of boolean values
                according to binary representation.
    byte_like:  bool, optional
                Control to verify that the integer is broken into a
                list of booleans that could be composed into a byte
                string object (i.e. length of list is divisible by 8),
                defaults to False.
    reverse:    bool, optional
                Control to reverse the order of the binary/boolean
                points.
    
    Returns
    -------
    bin_list:   list of bool
                List of boolean values cast from the binary
                representation of the integer passed to the
                function.
    """
    bin_string = format(number, '04b')
    bin_list = [x == '1' for x in bin_string[::-1]]
    # Extend List of Bytes if Needed
    if byte_like and ((len(bin_list) % 8) != 0):
        len_needed = ((len(bin_list)//8)+1) * 8
        apnd_list  = [False] * (len_needed - len(bin_list))
        bin_list.extend(apnd_list)
    # Reverse if Desired
    if reverse:
        bin_list.reverse()
    return bin_list

# Define Simple Function to Cast Binary Representation of IEEE 4-Byte FPS
def ieee4bytefps( binary_bytes, total_digits=7 ):
    """
    `ieee4bytefps`

    This function accepts a bytestring of 4 bytes and evaluates the
    IEEE Floating-Point value represented by the bytestring.

    Parameters
    ----------
    binary_bytes:   bytes
                    The 4-byte bytestring which should be cast
                    to a float using the IEEE floating-point standard.
    total_digits:   int, optional
                    Number of digits (i.e. decimal accuracy) which
                    should be evaluated, defaults to 7.
    """
    # Define the Internal Functions to Utilize
    def magnitude(x):
        return 0 if x==0 else int(math.floor(math.log10(abs(x)))) + 1
    def round_total_digits(x, digits=7):
        return round(x, digits - magnitude(x))
    # Perform Calculation
    return round_total_digits(  x=struct.unpack('>f', binary_bytes)[0],
                                digits=total_digits )


# END