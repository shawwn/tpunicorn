Welcome to tpudiepie!
=====================

`tpudiepie` is a Python (2.7 and 3.4+) library and command-line program
for managing TPUs.


Commands
========

`pu babysit`
------------

`pu babysit` recreates a TPU if it preempts.
    
Example:
    
.. code:: sh
      # In one terminal window, simulate a training session...
      while True; do bash -c 'echo My Training Session... ; sleep 10000'; echo 'restarted'; sleep 1; done
    

.. code:: sh
      # In a separate window, babysit a TPU...
      pu babysit my-tpu -c 'pkill -9 -f "My Training Session"'
