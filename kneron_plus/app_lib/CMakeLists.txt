# auto-scan sub-folders

SUBDIRLIST(SUBDIRS ${CMAKE_CURRENT_SOURCE_DIR} "*")

FOREACH(subdir ${SUBDIRS})
  if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/${subdir}/CMakeLists.txt)
    ADD_SUBDIRECTORY(${subdir})
  endif()
ENDFOREACH()

