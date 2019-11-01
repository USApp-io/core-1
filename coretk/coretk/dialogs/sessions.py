import logging
import tkinter as tk
from tkinter.ttk import Scrollbar, Treeview

from core.api.grpc import core_pb2
from coretk.dialogs.dialog import Dialog
from coretk.images import ImageEnum, Images


class SessionsDialog(Dialog):
    def __init__(self, master, app):
        """
        create session table instance

        :param coretk.coregrpc.CoreGrpc grpc: coregrpc
        :param root.master master:
        """
        super().__init__(master, app, "Sessions", modal=True)
        self.selected = False
        self.selected_id = None
        self.tree = None
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.draw_description()
        self.draw_tree()
        self.draw_buttons()

    def draw_description(self):
        """
        write a short description
        :return: nothing
        """
        label = tk.Label(
            self,
            text="Below is a list of active CORE sessions. Double-click to \n"
            "connect to an existing session. Usually, only sessions in \n"
            "the RUNTIME state persist in the daemon, except for the \n"
            "one you might be concurrently editting.",
        )
        label.grid(row=0, sticky="ew", pady=5)

    def draw_tree(self):
        self.tree = Treeview(self, columns=("id", "state", "nodes"), show="headings")
        self.tree.grid(row=1, sticky="nsew")
        self.tree.column("id", stretch=tk.YES)
        self.tree.heading("id", text="ID")
        self.tree.column("state", stretch=tk.YES)
        self.tree.heading("state", text="State")
        self.tree.column("nodes", stretch=tk.YES)
        self.tree.heading("nodes", text="Node Count")

        response = self.app.core_grpc.core.get_sessions()
        logging.info("sessions: %s", response)
        for index, session in enumerate(response.sessions):
            state_name = core_pb2.SessionState.Enum.Name(session.state)
            self.tree.insert(
                "",
                tk.END,
                text=str(session.id),
                values=(session.id, state_name, session.nodes),
            )
        self.tree.bind("<Double-1>", self.on_selected)
        self.tree.bind("<<TreeviewSelect>>", self.click_select)

        yscrollbar = Scrollbar(self, orient="vertical", command=self.tree.yview)
        yscrollbar.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=yscrollbar.set)

        xscrollbar = Scrollbar(self, orient="horizontal", command=self.tree.xview)
        xscrollbar.grid(row=2, sticky="ew", pady=5)
        self.tree.configure(xscrollcommand=xscrollbar.set)

    def draw_buttons(self):
        frame = tk.Frame(self)
        for i in range(4):
            frame.columnconfigure(i, weight=1)
        frame.grid(row=3, sticky="ew")
        b = tk.Button(
            frame,
            image=Images.get(ImageEnum.DOCUMENTNEW),
            text="New",
            compound=tk.LEFT,
            command=self.click_new,
        )
        b.grid(row=0, padx=2, sticky="ew")
        b = tk.Button(
            frame,
            image=Images.get(ImageEnum.FILEOPEN),
            text="Connect",
            compound=tk.LEFT,
            command=self.click_connect,
        )
        b.grid(row=0, column=1, padx=2, sticky="ew")
        b = tk.Button(
            frame,
            image=Images.get(ImageEnum.EDITDELETE),
            text="Shutdown",
            compound=tk.LEFT,
            command=self.click_shutdown,
        )
        b.grid(row=0, column=2, padx=2, sticky="ew")
        b = tk.Button(frame, text="Cancel", command=self.click_new)
        b.grid(row=0, column=3, padx=2, sticky="ew")

    def click_new(self):
        self.app.core_grpc.create_new_session()
        self.destroy()

    def click_select(self, event):
        item = self.tree.selection()
        session_id = int(self.tree.item(item, "text"))
        self.selected = True
        self.selected_id = session_id

    def click_connect(self):
        """
        if no session is selected yet, create a new one else join that session

        :return: nothing
        """
        if self.selected and self.selected_id is not None:
            self.join_session(self.selected_id)
        elif not self.selected and self.selected_id is None:
            self.click_new()
        else:
            logging.error("sessions invalid state")

    def click_shutdown(self):
        """
        if no session is currently selected create a new session else shut the selected
        session down.

        :return: nothing
        """
        if self.selected and self.selected_id is not None:
            self.shutdown_session(self.selected_id)
        elif not self.selected and self.selected_id is None:
            self.click_new()
        else:
            logging.error("querysessiondrawing.py invalid state")

    def join_session(self, session_id):
        response = self.app.core_grpc.core.get_session(session_id)
        self.app.core_grpc.session_id = session_id
        self.app.core_grpc.core.events(session_id, self.app.core_grpc.log_event)
        logging.info("entering session_id %s.... Result: %s", session_id, response)
        self.destroy()

    def on_selected(self, event):
        item = self.tree.selection()
        sid = int(self.tree.item(item, "text"))
        self.join_session(sid)

    def shutdown_session(self, sid):
        self.app.core_grpc.terminate_session(sid)
        self.click_new()
        self.destroy()
