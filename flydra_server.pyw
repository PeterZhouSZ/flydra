#!/usr/bin/env python
import sys
import thread
import time
import socket
import os
import Pyro.core
import DynamicImageCanvas
Pyro.config.PYRO_MULTITHREADED = 0 # No multithreading!

Pyro.config.PYRO_TRACELEVEL = 3
Pyro.config.PYRO_USER_TRACELEVEL = 3
Pyro.config.PYRO_DETAILED_TRACEBACK = 1
Pyro.config.PYRO_PRINT_REMOTE_TRACEBACK = 1

from wxPython.wx import *
from wxPython.lib import newevent
from wxPython.xrc import *

RESDIR = os.path.split(os.path.abspath(sys.argv[0]))[0]
RESFILE = os.path.join(RESDIR,'flydra_server.xrc')
hydra_image_file = os.path.join(RESDIR,'hydra.gif')
RES = wxXmlResource(RESFILE)

class FlydraBrainPyroServer( Pyro.core.ObjBase ):
    def post_init(self,wxApp):
        self.wxApp = wxApp
        self.servlets = {}
        dynamic_image_panel = XRCCTRL(self.wxApp.main_panel,"DynamicImagePanel") # get container
        self.cam_image_canvas = DynamicImageCanvas.DynamicImageCanvas(dynamic_image_panel,-1) # put GL window in container
        #self.cam_image_canvas = wxButton(dynamic_image_panel,-1,"Button") # put GL window in container

        box = wxBoxSizer(wxVERTICAL)
        #box.Add(self.cam_image_canvas,1,wxEXPAND|wxSHAPED) # keep aspect ratio
        box.Add(self.cam_image_canvas,1,wxEXPAND)
        dynamic_image_panel.SetSizer(box)
        dynamic_image_panel.Layout()

        self.update_wx()
    def update_wx(self):
        self.wxApp.statusbar.SetStatusText('%d camera servlet(s)'%len(self.servlets),2)
    def make_new_camera_servlet(self):
        cam_serv = CameraServlet()
        cam_serv.post_init( self.wxApp, self )
        daemon = self.getDaemon()
        URI=daemon.connect(cam_serv) # start serving cam_serv
        self.servlets[cam_serv]=None
        self.update_wx()
        return URI
    def unregister_servlet(self,servlet):
        """To be called by the servlet upon it's close()"""
        del self.servlets[servlet]
        self.update_wx()
    def check_servlets(self):
        for servlet in self.servlets.keys(): # copy servlet in case we have to delete it
            if hasattr(servlet,'caller'): # XXX when servlet being closed, check_servlets may still be called?! (implies threads!)
                if not servlet.caller.connected:
                    servlet.close()
                    # XXX should run this in a new thread to keep other tasks going!
                    dlg = wxMessageDialog(self.wxApp.main_panel, 'Camera %s unexpectedly disconneted'%servlet.cam_id,
                                          'Unexpected camera disconnection', wxOK | wxICON_ERROR)
                    dlg.ShowModal()
                    dlg.Destroy()

class CameraServlet( Pyro.core.ObjBase ):
    """Communication between camPanel and Pyro"""
    
    # -=-=-=-=-= remotely called methods start -=-=-=-=-=
    
    def set_cam_info(self, cam_id, scalar_control_info):
        """Set up servlet's representation of the client camera.
        
        This is called once immediately after connection by the camera
        client.
        
        """
        
        self.cam_id = cam_id
        self.scalar_control_info = scalar_control_info

        self.my_container = self.wxApp.all_cam_panel
        self.start_time = time.time()

        self.n_frames = 0
        self.last_measurement_time = time.time()
        self.command_queue = {}

        self.init_gui()

    def get_commands(self):
        """Return queue of commands for client camera."""
        result = self.command_queue.items()
        self.command_queue = {} # clear queue
        return result

    def push_image(self, image):
        if self.my_id is None: # make sure we're not quitting!
            return
        self.dyn_canv.update_image(self.my_id,image)
        self.n_frames += 1

    def set_current_fps(self, acquired_fps):
        #self.current_fps = fps
        acquired_fps_label = XRCCTRL(self.camPanel,'acquired_fps_label') # get container
        acquired_fps_label.SetLabel('Frames per second (acquired): %.1f'%acquired_fps)
        
        now = time.time()
        elapsed = now-self.last_measurement_time
        self.last_measurement_time = now
        displayed_fps = self.n_frames/elapsed
        displayed_fps_label = XRCCTRL(self.camPanel,'displayed_fps_label') # get container
        displayed_fps_label.SetLabel('Frames per second (displayed): %.1f'%displayed_fps)
        
        self.n_frames = 0
        
    def close(self, dummy_event=None):
        if self.my_id is not None: # only close once
            self.command_queue['quit']=True
            self.parent.unregister_servlet(self)
            if hasattr(self,'camPanel'):
                self.camPanel.DestroyChildren()
                self.camPanel.Destroy()
                del self.camPanel
            try:
                self.dyn_canv.delete_image(self.my_id)
            except KeyError:
                pass
            self.my_id = None

    # -=-=-=-=-= remotely called methods end -=-=-=-=-=
        
    def post_init(self, wxApp, parent):
        self.parent = parent
        self.wxApp = wxApp
        self.dyn_canv = self.parent.cam_image_canvas
        self.my_id = id(self)

    def init_gui(self):
        """build GUI"""
        
        self.camPanel = RES.LoadPanel(self.my_container,"PerCameraPanel")
        # Add myself to my_container's sizer
        acp_box = self.my_container.GetSizer()
        acp_box.Add(self.camPanel,1,wxEXPAND | wxALL,border=10)
        #self.my_container.Layout() #???

        if 0:
            box = self.camPanel.GetSizer()
            static_box = box.GetStaticBox()
            static_box.SetLabel( 'Camera ID: %s'%self.cam_id )

        self.caller= self.daemon.getLocalStorage().caller # XXX Pyro hack??
        caller_addr= self.caller.addr
        caller_ip, caller_port = caller_addr
        fqdn = socket.getfqdn(caller_ip)

        cam_info_label = XRCCTRL(self.camPanel,'cam_info_label')
        cam_id_string = 'camera %s:%d'%(fqdn,caller_port)
        cam_info_label.SetLabel(cam_id_string)

        quit_camera = XRCCTRL(self.camPanel,"quit_camera") # get container
#        EVT_BUTTON(quit_camera, quit_camera.GetId(), self.disconnect_camera)
        EVT_BUTTON(quit_camera, quit_camera.GetId(), self.close)
        
        per_cam_controls_panel = XRCCTRL(self.camPanel,"PerCameraControlsContainer") # get container
        box = wxBoxSizer(wxVERTICAL)

        for param in self.scalar_control_info:
            current_value, min_value, max_value = self.scalar_control_info[param]
            scalarPanel = RES.LoadPanel(per_cam_controls_panel,"ScalarControlPanel") # frame main panel
            box.Add(scalarPanel,1,wxEXPAND)
            
            label = XRCCTRL(scalarPanel,'scalar_control_label')
            label.SetLabel( param )
            
            slider = XRCCTRL(scalarPanel,'scalar_control_slider')
            #slider.SetToolTip(wxToolTip('adjust %s'%param))
            slider.SetRange( min_value, max_value )
            slider.SetValue( current_value )
            
            class ParamSliderHelper:
                def __init__(self, name, slider, parent):
                    self.name=name
                    self.slider=slider
                    self.parent = parent
                def onScroll(self, event):
                    self.parent.command_queue[self.name] = self.slider.GetValue()
            
            psh = ParamSliderHelper(param,slider,self)
            EVT_COMMAND_SCROLL(slider, slider.GetId(), psh.onScroll)
        
        per_cam_controls_panel.SetSizer(box)
        self.my_container.Layout()

class App(wxApp):
    def OnInit(self,*args,**kw):
    
        wxInitAllImageHandlers()
        frame = wxFrame(None, -1, "Flydra Main Brain",size=(800,600))
        
        self.statusbar = frame.CreateStatusBar()
        self.statusbar.SetFieldsCount(3)
        menuBar = wxMenuBar()
        filemenu = wxMenu()
        ID_quit = wxNewId()
        filemenu.Append(ID_quit, "Quit\tCtrl-Q", "Quit application")
        EVT_MENU(self, ID_quit, self.OnQuit)
        menuBar.Append(filemenu, "&File")
        frame.SetMenuBar(menuBar)

        self.main_panel = RES.LoadPanel(frame,"FLYDRA_PANEL") # make frame main panel
        self.main_panel.SetFocus()

        frame_box = wxBoxSizer(wxVERTICAL)
        frame_box.Add(self.main_panel,1,wxEXPAND)
        frame.SetSizer(frame_box)
        frame.Layout()

        nb = XRCCTRL(self.main_panel,"MAIN_NOTEBOOK")
        self.cam_preview_panel = RES.LoadPanel(nb,"CAM_PREVIEW_PANEL") # make camera preview panel
        nb.AddPage(self.cam_preview_panel,"Camera Preview/Settings")
        
        temp_panel = RES.LoadPanel(nb,"UNDER_CONSTRUCTION_PANEL") # make camera preview panel
        nb.AddPage(temp_panel,"3D Calibration")

        temp_panel = RES.LoadPanel(nb,"UNDER_CONSTRUCTION_PANEL") # make camera preview panel
        nb.AddPage(temp_panel,"Record raw video")

        temp_panel = RES.LoadPanel(nb,"UNDER_CONSTRUCTION_PANEL") # make camera preview panel
        nb.AddPage(temp_panel,"Realtime 3D tracking")

        #####################################

        self.all_cam_panel = XRCCTRL(self.cam_preview_panel,"AllCamPanel")

        acp_box = wxBoxSizer(wxHORIZONTAL) # all camera panel (for camera controls, e.g. gain)
        self.all_cam_panel.SetSizer(acp_box)
        
        #acp_box.Add(wxStaticText(self.all_cam_panel,-1,"This is the main panel"),0,wxEXPAND)
        self.all_cam_panel.Layout()

        #########################################

        frame.SetAutoLayout(true)

        frame.Show()
        self.SetTopWindow(frame)
        self.frame = frame

        self.start_pyro_server()

        #EVT_IDLE(self, self.OnTimer)
        
        ID_Timer  = wxNewId()
        self.timer = wxTimer(self,      # object to send the event to
                             ID_Timer)  # event id to use
        EVT_TIMER(self,  ID_Timer, self.OnTimer)
        self.timer.Start(100)
        
        return True
    
    def OnQuit(self, event):
        self.frame.Close(True)

    def OnTimer(self, event):
        self.daemon.handleRequests(0) # don't block
        self.flydra_brain.check_servlets()
        self.flydra_brain.cam_image_canvas.OnDraw()
        
    def start_pyro_server(self):
        Pyro.core.initServer(banner=0)
        hostname = socket.gethostbyname(socket.gethostname())
        fqdn = socket.getfqdn(hostname)
        port = 9832
        self.daemon = Pyro.core.Daemon(host=hostname,port=port)
        self.flydra_brain = FlydraBrainPyroServer()
        self.flydra_brain.post_init(self)
        URI=self.daemon.connect(self.flydra_brain,'flydra_brain')
        self.statusbar.SetStatusText("flydra_brain at %s:%d"%(fqdn,port), 1)
        self.frame.SetFocus()

def main():
    #app = App(redirect=1,filename='flydra_log.txt')
    app = App()
    app.MainLoop()

if __name__ == '__main__':
    main()

