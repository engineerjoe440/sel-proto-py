"""
selprotopy: A Protocol Binding Suite for the SEL Protocol Suite.

Supports:
  - SEL Fast Meter
  - SEL Fast Message
  - SEL Fast Operate

Author(s):
  - Joe Stanley: joe_stanley@selinc.com

Homepage: https://github.com/engineerjoe440/sel-proto-py

SEL Protocol Application Guide: https://selinc.com/api/download/5026/?lang=en
"""

# Standard Imports
import time
import telnetlib

# Local Imports
try:
    from . import commands
    from . import protoparser
    from . import telnetlib_support
except ImportError:
    import commands
    import protoparser
    import telnetlib_support

# Describe Package for External Interpretation
_name_ = "selprotopy"
_version_ = "0.0"
__version__ = _version_  # Alias the Version String

# `telnetlib` Discards Null Characters, but SEL Protocol Requires them
telnetlib.Telnet.process_rawq = telnetlib_support.process_rawq


# Define Simple Polling Client
class SelClient():
    """
    `SelClient` Class

    The basic polling class intended to interact with an SEL relay which has
    already been connected to by way of a Telnet or Serial connection using one
    of the following Python libraries:

    - telnetlib     https://docs.python.org/3/library/telnetlib.html
    - pyserial      https://pyserial.readthedocs.io/en/latest/pyserial.html

    Parameters
    ----------
    connApi:            [telnetlib.Telnet, serial.Serial]
                        Telnet or Serial API which will be used to communicate
                        with the SEL relay.
    autoconfig_now:     bool, optional
                        Control to activate automatic configuration with the
                        connected relay at time of class initialization, this
                        should normally be set to True to allow autoconfig.
                        Defaults to True
    validConnChecks:    int, optional
                        Integer control to indicate maximum number of
                        connection attempts should be issued to relay in the
                        process of verifying established connection(s).
                        Defaults to 5
    interdelay:         float, optional
                        Floating control which describes the amount of time in
                        seconds between iterative connection verification
                        attempts. Defaults to 0.025 (seconds)
    verbose:            bool, optional
                        Control to dictate whether verbose printing operations
                        should be used (often for debugging and learning 
                        purposes). Defaults to False
    
    Attributes
    ----------
    conn:       [telnetlib.Telnet, serial.Serial]
                Connection API
    verbose:    bool
                Verbose information printing record (set by `verbose`)
    check:      int
                Number of connection attempts before indicating failure
                (set by `validConnChecks`)
    delay:      float
                Time (in seconds) to delay between connection attempts
                (set by `interdelay`)
    fid:        str
                Relay's described Firmware ID string (set by connection with
                relay)
    bfid:       str
                Relay's described BFID string (set by connection with relay)
    cid:        str
                Relay's described CID string (set by connection with relay)
    devid:      str
                Relay's described DEVID string (set by connection with relay)
    partno:     str
                Relay's described part number string (set by connection with
                relay)
    config:     str
                Relay's described configuration string (set by connection with
                relay)
    """
    
    def __init__( self, connApi, autoconfig_now=True, validConnChecks=5,
                  interdelay=0.025, verbose=False, debug=False ):
        """ Initialization Method - Returns False if Connection Fails """
        # Initialize Inputs
        self.conn = connApi
        self.verbose = verbose
        self.check = validConnChecks
        self.delay = interdelay
        self.debug = debug
        
        # Define Basic Parameter Defaults
        self.fid     = ''
        self.bfid    = ''
        self.cid     = ''
        self.devid   = ''
        self.partno  = ''
        self.config  = ''
        
        # Define the Various Command Defaults
        self.fmconfigcommand1   = commands.FM_CONFIG_BLOCK
        self.fmcommand1         = commands.FM_DEMAND_CONFIG_BLOCK
        self.fmconfigcommand2   = commands.FM_PEAK_CONFIG_BLOCK
        self.fmcommand2         = commands.FAST_METER_REGULAR
        self.fmconfigcommand3   = commands.FAST_METER_DEMAND
        self.fmcommand3         = commands.FAST_METER_PEAK_DEMAND
        self.fopcommandinfo     = commands.FO_CONFIG_BLOCK
        self.fmsgcommandinfo    = commands.FAST_MSG_CONFIG_BLOCK
        
        # Allocate Space for Relay Definition Responses
        self.fastMeterDef       = None
        self.fastDemandDef      = None
        self.fastPkDemandDef    = None
        
        # Verify Connection by Searching for Prompt
        if verbose: print('Verifying Connection...')
        if not self._verify_connection():
            raise ValueError("Could not verify connection.")  # TODO: Custom exception
        if verbose: print('Connection Verified.')
        self.quit()
        if autoconfig_now:
            # Run Auto-Configuration
            self.autoconfig(verbose=debug)
        
    # Define Connectivity Check Method
    def _verify_connection( self ):
        # Set Default Indication
        connected = False
        # Iteratively attempt to see relay's response
        for _ in range(self.check):
            self.conn.write( commands.CR )
            response = self.conn.read_until( commands.CR )
            if commands.LEVEL_0 in response:
                # Relay Responded
                connected = True
                break
            else:
                time.sleep( self.delay )
        # Return Status
        return connected
    
    # Define Method to Read All Data to Next Relay Prompt
    def _read_to_prompt( self, prompt_str=commands.PROMPT ):
        response = self.conn.read_until( commands.PROMPT )
        if self.debug: print(response)
        return response
    
    # Define Method to Read All Data After a Command (and to next relay prompt)
    def _read_command_response( self, command, prompt_str=commands.PROMPT ):
        response = b''
        while response.find(command) == -1:
            response += self._read_to_prompt( prompt_str=prompt_str )
        return response
    
    # Define Method to Attempt Reading Everything (only for telnetlib)
    def _read_everything( self ):
        response = self.conn.read_very_eager()
        if self.debug: print(response)
        return response
    
    # Define Method to Identify Current Access Level
    def access_level(self):
        """
        `access_level`

        Simple method to identify what the current access level
        is for the connected relay. Provides an integer and
        string.

        Returns
        -------
        int:    Integer representing the access level
                as a value in the range of [0, 1, 2, 3]
        desc:   String describing the access level,
                will return empty string for level-0.
        """
        # Retrieve Prompt Twice
        self.conn.write( commands.CR )
        resp = self._read_to_prompt()
        self.conn.write( commands.CR )
        resp += self._read_to_prompt()
        # Look for Each Level, Return Highest Found
        if commands.LEVEL_C in resp:
            return (3, 'CAL')
        elif commands.LEVEL_2 in resp:
            return (2, '2AC')
        elif commands.LEVEL_1 in resp:
            return (1, 'ACC')
        else:
            return (0, '')
    
    # Define Method to Return to Access Level 0
    def quit(self):
        """
        `quit` Method
        
        Simple method to send the QUIT command to an
        actively connected relay.
        
        See Also
        --------
        access_level_1      : Elevate permission to ACC
        access_level_2      : Elevate permission to 2AC
        """
        self.conn.write( commands.QUIT )
        self._read_to_prompt( commands.LEVEL_0 )
    
    # Define Method to Access Level 1
    def access_level_1(self, level_1_pass=commands.PASS_ACC, **kwargs):
        """
        `access_level_1` Method
        
        Used to elevate connection privileges with the connected
        relay to ACC with the appropriate password specified. If
        called when current access level is greater than ACC, this
        method will deescalate the permission level to ACC.
        
        See Also
        --------
        quit                : Relinquish all permission with relay
        access_level_2      : Elevate permission to 2AC
        
        Parameters
        ----------
        level_1_pass:       str, optional
                            Password necessary to access the ACC
                            level, only required if accessing ACC
                            from level 0 (i.e. logging in).
        
        Returns
        -------
        success:            bool
                            Indicator of whether the login failed.
        """
        # Identify Current Access Level
        time.sleep( self.delay )
        level, name = self.access_level()
        if self.debug: print("Logging in to ACC")
        self.conn.write( commands.GO_ACC )
        # Provide Password
        if level == 0:
            time.sleep( int(self.delay * 3) )
            self.conn.write( level_1_pass + commands.CR )
            time.sleep( self.delay )
        resp = self._read_to_prompt( commands.LEVEL_0 )
        if b'Invalid' in resp:
            if self.debug: print("Log-In Failed")
            return False
        else:
            if self.debug: print("Log-In Succeeded")
            return True
    
    # Define Method to Access Level 2
    def access_level_2(self, level_2_pass=commands.PASS_2AC, **kwargs):
        """
        `access_level_2` Method
        
        Used to elevate connection privileges with the connected
        relay to 2AC with the appropriate password specified. If
        called when current access level is greater than 2AC, this
        method will deescalate the permission level to 2AC.
        
        See Also
        --------
        quit                : Relinquish all permission with relay
        access_level_1      : Elevate permission to ACC
        
        Parameters
        ----------
        level_2_pass:       str, optional
                            Password necessary to access the 2AC
                            level, only required if accessing 2AC
                            from level 1 (i.e. logging in).
        
        Returns
        -------
        success:            bool
                            Indicator of whether the login failed.
        """
        # Identify Current Access Level
        level, name = self.access_level()
        # Provide Password
        if level == 0:
            if not self.access_level_1( **kwargs ):
                return False
        if self.debug: print("Logging in to 2AC")
        self.conn.write( commands.GO_2AC )
        if level in [0, 1]:
            time.sleep( int(self.delay * 3) )
            self.conn.write( level_2_pass + commands.CR )
            time.sleep( self.delay )
        resp = self._read_to_prompt( commands.LEVEL_0 )
        if b'Invalid' in resp:
            if self.debug: print("Log-In Failed")
            return False
        else:
            if self.debug: print("Log-In Succeeded")
            return True
    
    # Define Method to Perform Auto-Configuration Process
    def autoconfig( self, verbose=False, **kwargs ):
        """
        `autoconfig` Method
        
        Method to operate the standard auto-configuration process
        with a connected relay to identify the system parameters of
        the relay. This includes:
        
        - FID
        - BFID
        - CID
        - DEVID
        - PARTNO
        - CONFIG
        - Relay Definition Block
        
        This method also automatically interprets the following fast
        meter blocks by way of separate method calls.
        
        - Fast Meter Configuration Block
        - Fast Meter Demand Configuration Block
        - Fast Meter Peak Demand Configuration Block
        
        See Also
        --------
        autoconfig_fastmeter            : Auto Configuration for Fast Meter
        autoconfig_fastmeter_demand     : Auto Configuration for Fast Meter 
                                            Demand
        autoconfig_fastmeter_peakdemand : Auto Configuration for Fast Meter
                                            Peak Demand
        
        Parameters
        ----------
        verbose:        bool, optional
                        Control to dictate whether verbose printing operations
                        should be used (often for debugging and learning
                        purposes). Defaults to False
        
        Returns
        -------
        fid:            str
                        Relay's Configured FID as Confirmation of Successful
                        Automatic Configuration
        """
        # Determine if Level 0, and Escalate Accordingly
        if self.access_level()[0] == 0:
            # Access Level 1 Required to Request DNA
            self.access_level_1( **kwargs )
        # Request Relay Definition
        self.conn.write( commands.RELAY_DEFENITION + commands.CR )
        definition = protoparser.RelayDefinitionBlock(
            self._read_command_response(commands.RELAY_DEFENITION),
                                        verbose=verbose)
        # Load the Relay Definition Information
        self.fmconfigcommand1   = definition['fmcommandinfo'][0]['configcommand']
        self.fmcommand1         = definition['fmcommandinfo'][0]['command']
        self.fmconfigcommand2   = definition['fmcommandinfo'][1]['configcommand']
        self.fmcommand2         = definition['fmcommandinfo'][1]['command']
        self.fmconfigcommand3   = definition['fmcommandinfo'][2]['configcommand']
        self.fmcommand3         = definition['fmcommandinfo'][2]['command']
        self.fopcommandinfo     = definition['fopcommandinfo']
        self.fmsgcommandinfo    = definition['fmsgcommandinfo']
        # Request the Meter Blocks
        self.autoconfig_fastmeter( verbose=verbose )
        self.autoconfig_fastmeter_demand( verbose=verbose )
        self.autoconfig_fastmeter_peakdemand( verbose=verbose )
        # Request Relay ENA Block
        # TODO
        # Request Relay DNA Block
        self.conn.write( commands.DNA )
        self.dnaDef = protoparser.RelayDnaBlock(self._read_to_prompt(),
                                                encoding='utf-8',
                                                verbose=verbose)
        # Request Relay BNA Block
        ## TODO
        # Request Relay ID Block
        self.conn.write( commands.ID )
        id_block = protoparser.RelayIdBlock(self._read_to_prompt(),
                                            encoding='utf-8',
                                            verbose=verbose)
        # Store Relay Information
        self.fid    = id_block['FID']
        self.bfid   = id_block['BFID']
        self.cid    = id_block['CID']
        self.devid  = id_block['DEVID']
        self.partno = id_block['PARTNO']
        self.config = id_block['CONFIG']
        # Return the Relay's FID
        return self.fid

    # Define Method to Run the Fast Meter Configuration
    def autoconfig_fastmeter(self, verbose=False):
        """
        `autoconfig_fastmeter` Method

        Method to operate the standard auto-configuration process
        with a connected relay to identify the standard fast meter
        parameters of the relay.

        See Also
        --------
        autoconfig                      : Relay Auto Configuration
        autoconfig_fastmeter_demand     : Auto Configuration for Fast Meter Demand
        autoconfig_fastmeter_peakdemand : Auto Configuration for Fast Meter Peak Demand

        Parameters
        ----------
        verbose:        bool, optional
                        Control to dictate whether verbose printing operations
                        should be used (often for debugging and learning purposes).
                        Defaults to False
        """
        # Fast Meter
        self.conn.write( self.fmconfigcommand1 + commands.CR )
        self.fastMeterDef = protoparser.FastMeterConfigurationBlock(
                                self._read_to_prompt(), verbose=verbose)
    
    # Define Method to Run the Fast Meter Demand Configuration
    def autoconfig_fastmeter_demand(self, verbose=False):
        """
        `autoconfig_fastmeter_demand` Method

        Method to operate the standard auto-configuration process
        with a connected relay to identify the fast meter demand
        parameters of the relay.

        See Also
        --------
        autoconfig                      : Relay Auto Configuration
        autoconfig_fastmeter            : Auto Configuration for Fast Meter
        autoconfig_fastmeter_peakdemand : Auto Configuration for Fast Meter Peak Demand

        Parameters
        ----------
        verbose:        bool, optional
                        Control to dictate whether verbose printing operations
                        should be used (often for debugging and learning purposes).
                        Defaults to False
        """
        # Fast Meter Demand
        self.conn.write( self.fmconfigcommand2 + commands.CR )
        self.fastDemandDef = protoparser.FastMeterConfigurationBlock(
                                self._read_to_prompt(), verbose=verbose)

    # Define Method to Run the Fast Meter Peak Demand Configuration
    def autoconfig_fastmeter_peakdemand(self, verbose=False):
        """
        `autoconfig_fastmeter_peakdemand` Method

        Method to operate the standard auto-configuration process
        with a connected relay to identify the fast meter peak demand
        parameters of the relay.

        See Also
        --------
        autoconfig                      : Relay Auto Configuration
        autoconfig_fastmeter            : Auto Configuration for Fast Meter
        autoconfig_fastmeter_demand     : Auto Configuration for Fast Meter Demand

        Parameters
        ----------
        verbose:        bool, optional
                        Control to dictate whether verbose printing operations
                        should be used (often for debugging and learning purposes).
                        Defaults to False
        """
        # Fast Meter Peak Demand
        self.conn.write( self.fmconfigcommand3 + commands.CR )
        self.fastPkDemandDef = protoparser.FastMeterConfigurationBlock(
                                self._read_to_prompt(), verbose=verbose)

    # Define Method to Perform Fast Meter Polling
    def poll_fast_meter(self, minAccLevel=0, verbose=False, **kwargs):
        """
        `poll_fast_meter` Method

        Method to poll the connected relay with the configured protocol
        settings (use `autoconfig` method to configure protocol settings).

        See Also
        --------
        autoconfig                      : Relay Auto Configuration

        Parameters
        ----------
        minAccLevel:    int, optional
                        Control to specify whether a minimum access level must be
                        obtained before polling should be performed.
        verbose:        bool, optional
                        Control to dictate whether verbose printing operations
                        should be used (often for debugging and learning purposes).
                        Defaults to False
        """
        # Verify that Configuration is Valid
        if self.fastMeterDef == None:
            # TODO: Add Custom Exception to be More Explicit
            raise ValueError("Client has not been auto-configured yet!")
        # Raise to Appropriate Access Level if Needed
        if minAccLevel == 1:
            self.access_level_1( **kwargs )
        if minAccLevel == 2:
            self.access_level_2( **kwargs )
        # Poll Client for Data
        self.conn.write( self.fmcommand1 + commands.CR )
        response = protoparser.FastMeterBlock(  self._read_command_response(
                                                    self.fmcommand1),
                                                self.fastMeterDef,
                                                self.dnaDef,
                                                verbose=verbose )
        # Return the Response
        return response




if __name__ == '__main__':
    print('Establishing Connection...')
    with telnetlib.Telnet('192.168.254.10', 23) as tn:
        print('Initializing Client...')
        poller = SelClient( tn, verbose=True)  # , debug=True )
        d = None
        for _ in range(10):
            d = poller.poll_fast_meter()  # verbose=True)
            for name, value in d['analogs'].items():
                print(name, value)
            time.sleep(1)
        print(d['digitals'])

# END